"""Native HA config flows, coordinator, entities and lifecycle tests."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.honeywell_mbus import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.honeywell_mbus.api import (
    HoneywellMbusClient,
    IdentityError,
    MeterSample,
    TransportError,
    UnsupportedMeterError,
    decode_frame,
)
from custom_components.honeywell_mbus.config_flow import (
    HoneywellConfigFlow,
    HoneywellOptionsFlow,
    connection_schema,
    normalize_host,
    validate_connection,
)
from custom_components.honeywell_mbus.const import CONF_SERIAL, DOMAIN
from custom_components.honeywell_mbus.coordinator import HoneywellCoordinator
from custom_components.honeywell_mbus.diagnostics import async_get_config_entry_diagnostics
from custom_components.honeywell_mbus.sensor import async_setup_entry as sensor_setup


@pytest.fixture
def sample(frame):
    return MeterSample(decode_frame(frame, 1), datetime.now(UTC), 0.2, 1)


@pytest.fixture
def client(sample):
    return SimpleNamespace(async_read=AsyncMock(return_value=sample), async_close=AsyncMock())


@pytest.fixture
def flow(hass):
    flow = HoneywellConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": "user"}
    return flow


def test_schema_defaults_and_host_normalization():
    assert connection_schema()({"host": " METER.Example. "}) == {
        "host": " METER.Example. ",
        "port": 8000,
        "primary_address": 1,
    }
    assert normalize_host("::1") == "::1"
    assert normalize_host(" METER.Example. ") == "meter.example"


@pytest.mark.parametrize(
    "host",
    [
        "",
        "https://device/",
        "device/path",
        "host name",
        "a?b",
        "user@device",
        "[::1]",
        "meter:8000",
    ],
)
def test_host_invalid(host):
    with pytest.raises(vol.Invalid):
        normalize_host(host)


@pytest.mark.parametrize(
    "data",
    [
        {"host": "meter", "port": 0},
        {"host": "meter", "port": 65536},
        {"host": "meter", "primary_address": 254},
        {"host": "meter", "primary_address": -1},
    ],
)
def test_schema_invalid(data):
    with pytest.raises(vol.Invalid):
        connection_schema()(data)


async def test_flow_initial_form(flow):
    result = await flow.async_step_user()
    assert result["type"] == "form" and result["step_id"] == "user"


async def test_flow_success(flow):
    found = {CONF_SERIAL: "12345678", "unique_id": "hon_eem400c_d_m_12345678"}
    with patch(
        "custom_components.honeywell_mbus.config_flow.validate_connection",
        AsyncMock(return_value=found),
    ):
        result = await flow.async_step_user(
            {"host": "METER.Example", "port": 8000, "primary_address": 1}
        )
    assert result["type"] == "create_entry" and result["data"]["host"] == "meter.example"
    assert result["data"]["serial_number"] == "12345678" and flow.unique_id == found["unique_id"]


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (TransportError("timeout"), "cannot_connect"),
        (UnsupportedMeterError("profile"), "unsupported_meter"),
    ],
)
async def test_flow_errors(flow, error, key):
    with patch(
        "custom_components.honeywell_mbus.config_flow.validate_connection",
        AsyncMock(side_effect=error),
    ):
        result = await flow.async_step_user({"host": "meter"})
    assert result["errors"] == {"base": key}


async def test_duplicate_endpoint_aborts_before_network(flow, entry):
    with patch(
        "custom_components.honeywell_mbus.config_flow.validate_connection", AsyncMock()
    ) as probe:
        from homeassistant.data_entry_flow import AbortFlow

        with pytest.raises(AbortFlow, match="already_configured"):
            await flow.async_step_user(
                {"host": "meter.invalid", "port": 8000, "primary_address": 2}
            )
        probe.assert_not_called()


async def test_duplicate_serial_different_gateway(flow, entry):
    from homeassistant.data_entry_flow import AbortFlow

    with patch(
        "custom_components.honeywell_mbus.config_flow.validate_connection",
        AsyncMock(return_value={CONF_SERIAL: "12345678", "unique_id": entry.unique_id}),
    ):
        with pytest.raises(AbortFlow, match="already_configured"):
            await flow.async_step_user({"host": "other.invalid"})


async def test_probe_real_tcp_releases_connection(meter_server):
    import custom_components.honeywell_mbus.config_flow as module

    real = HoneywellMbusClient
    with patch.object(
        module, "HoneywellMbusClient", side_effect=lambda *a, **kw: real(*a, **kw, initial_gap=0)
    ):
        found = await validate_connection(
            {"host": "127.0.0.1", "port": meter_server.port, "primary_address": 1}
        )
    assert found[CONF_SERIAL] == "12345678"


async def test_probe_releases_on_error(client):
    client.async_read.side_effect = TransportError("timeout")
    with patch(
        "custom_components.honeywell_mbus.config_flow.HoneywellMbusClient", return_value=client
    ):
        with pytest.raises(TransportError):
            await validate_connection({"host": "localhost", "port": 8000, "primary_address": 1})
    client.async_close.assert_awaited_once()


async def test_reconfigure_form(flow, entry):
    flow.context = {"source": "reconfigure", "entry_id": entry.entry_id}
    result = await flow.async_step_reconfigure()
    assert result["step_id"] == "reconfigure"


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (TransportError("timeout"), "cannot_connect"),
        (UnsupportedMeterError("profile"), "unsupported_meter"),
        (IdentityError("changed"), "wrong_meter"),
    ],
)
async def test_reconfigure_errors(flow, entry, error, key):
    flow.context = {"source": "reconfigure", "entry_id": entry.entry_id}
    with patch(
        "custom_components.honeywell_mbus.config_flow.validate_connection",
        AsyncMock(side_effect=error),
    ):
        result = await flow.async_step_reconfigure({"host": "new.invalid"})
    assert result["errors"] == {"base": key}


async def test_reconfigure_identity_and_success(flow, entry):
    flow.context = {"source": "reconfigure", "entry_id": entry.entry_id}
    with patch(
        "custom_components.honeywell_mbus.config_flow.validate_connection",
        AsyncMock(return_value={CONF_SERIAL: "other", "unique_id": "other"}),
    ):
        result = await flow.async_step_reconfigure({"host": "new.invalid"})
    assert result["errors"] == {"base": "wrong_meter"}
    with (
        patch(
            "custom_components.honeywell_mbus.config_flow.validate_connection",
            AsyncMock(return_value={CONF_SERIAL: "12345678", "unique_id": entry.unique_id}),
        ),
        patch.object(flow.hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await flow.async_step_reconfigure({"host": "new.invalid"})
    assert result["type"] == "abort" and result["reason"] == "reconfigure_successful"
    assert entry.data["host"] == "new.invalid" and entry.unique_id == "hon_eem400c_d_m_12345678"


async def test_options(hass, entry):
    options = HoneywellConfigFlow.async_get_options_flow(entry)
    assert isinstance(options, HoneywellOptionsFlow)
    assert options.automatic_reload
    options.hass = hass
    options.handler = entry.entry_id
    assert (await options.async_step_init())["type"] == "form"
    result = await options.async_step_init({"scan_interval": 3, "response_timeout": 2})
    assert result["data"] == {"scan_interval": 3, "response_timeout": 2.0}
    for bad in [
        {"scan_interval": 0, "response_timeout": 1},
        {"scan_interval": 2, "response_timeout": 0.1},
    ]:
        with pytest.raises(vol.Invalid):
            await options.async_step_init(bad)


async def test_coordinator_failure_recovery_and_cleanup(hass, entry, client, sample):
    coordinator = HoneywellCoordinator(hass, entry, client)
    assert coordinator.update_interval.total_seconds() == 2
    await coordinator.async_refresh()
    assert coordinator.data == sample and coordinator.last_update_success
    client.async_read.side_effect = TransportError("unreachable")
    await coordinator.async_refresh()
    assert not coordinator.last_update_success and coordinator.data == sample
    client.async_read.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    await coordinator.async_shutdown()
    client.async_close.assert_awaited_once()


async def test_setup_unload_and_reload(hass, entry, client):
    with (
        patch("custom_components.honeywell_mbus.HoneywellMbusClient", return_value=client),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()) as forward,
    ):
        assert await async_setup_entry(hass, entry) is None
    forward.assert_awaited_once()
    assert isinstance(entry.runtime_data, HoneywellCoordinator)
    with patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=False)):
        with pytest.raises(ConfigEntryError):
            await async_unload_entry(hass, entry)
        client.async_close.assert_not_awaited()
    with patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)):
        assert await async_unload_entry(hass, entry) is None
    client.async_close.assert_awaited_once()


async def test_failed_initial_setup_closes_client(hass, entry, client):
    client.async_read.side_effect = TransportError("offline")
    with patch("custom_components.honeywell_mbus.HoneywellMbusClient", return_value=client):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)
    client.async_close.assert_awaited_once()


async def test_failed_platform_setup_closes_client(hass, entry, client):
    with (
        patch("custom_components.honeywell_mbus.HoneywellMbusClient", return_value=client),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(side_effect=RuntimeError("platform")),
        ),
    ):
        with pytest.raises(RuntimeError):
            await async_setup_entry(hass, entry)
    client.async_close.assert_awaited_once()


async def test_sensors_native_values_and_stable_ids(hass, entry, client, sample):
    coordinator = HoneywellCoordinator(hass, entry, client)
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    entities = []
    await sensor_setup(hass, entry, lambda values: entities.extend(values))
    assert len(entities) == 20 and len({e.unique_id for e in entities}) == 20
    values = {e.entity_description.key: e.native_value for e in entities}
    assert values["power"] == 200 and values["energy"] == Decimal("1234.5")
    assert values["voltage_l1"] == 230 and values["current_l1"] == Decimal("1.3")
    assert (
        values["ct_ratio"] == 1 and values["read_duration"] == 0.2 and values["read_attempts"] == 1
    )
    assert values["last_read"] == sample.received_at and values["mbus_status"] == 0
    assert all(
        e.has_entity_name and e.device_info["identifiers"] == {(DOMAIN, sample.reading.unique_id)}
        for e in entities
    )
    assert sum(e.entity_description.entity_registry_enabled_default for e in entities) == 17
    assert all("meter.invalid" not in e.unique_id for e in entities)
    coordinator.async_set_update_error(UpdateFailed("offline"))
    assert all(not e.available for e in entities)
    coordinator.async_set_updated_data(sample)
    assert all(e.available for e in entities)
    await coordinator.async_shutdown()


async def test_diagnostics_redacted(hass, entry, client):
    coordinator = HoneywellCoordinator(hass, entry, client)
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert (
        data["config"]["host"] == "**REDACTED**"
        and data["config"]["serial_number"] == "**REDACTED**"
    )
    assert (
        data["profile"]["power_resolution_w"] == 100
        and data["profile"]["energy_resolution_kwh"] == 0.1
    )
    assert data["connection_healthy"] and data["transport"]["attempts"] == 1
    assert "12345678" not in str(data) and "meter.invalid" not in str(data)
    await coordinator.async_shutdown()


async def test_real_config_flow_manager(hass, client):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form" and result["step_id"] == "user"
    with patch(
        "custom_components.honeywell_mbus.config_flow.validate_connection",
        AsyncMock(side_effect=TransportError("offline")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "meter.invalid"}
        )
    assert result["errors"] == {"base": "cannot_connect"}
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_real_ha_platform_registry_reload_and_unload(hass, meter_server):
    from conftest import make_entry
    from homeassistant.helpers import entity_registry as er
    from homeassistant.setup import async_setup_component

    import custom_components.honeywell_mbus as integration

    entry = make_entry(
        data={
            "host": "127.0.0.1",
            "port": meter_server.port,
            "primary_address": 1,
            "serial_number": "12345678",
        },
        state=ConfigEntryState.NOT_LOADED,
    )
    real = HoneywellMbusClient
    with patch.object(
        integration,
        "HoneywellMbusClient",
        side_effect=lambda *a, **kw: real(*a, **kw, initial_gap=0),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert len(hass.states.async_entity_ids("sensor")) == 17
        registry = er.async_get(hass)
        ids = {
            item.unique_id: item.entity_id
            for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        assert len(ids) == 20
        power_id = ids["hon_eem400c_d_m_12345678_power"]
        energy_id = ids["hon_eem400c_d_m_12345678_energy"]
        assert hass.states.get(power_id).state == "200"
        assert hass.states.get(energy_id).attributes["state_class"] == "total_increasing"
        await entry.runtime_data.async_refresh()
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert {
            item.unique_id: item.entity_id
            for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        } == ids
        old_client = entry.runtime_data.client
        options_form = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            options_form["flow_id"], {"scan_interval": 4, "response_timeout": 2}
        )
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.update_interval.total_seconds() == 4
        assert old_client._closed
        owned_client = entry.runtime_data.client
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert owned_client._closed


@pytest.mark.parametrize("step", ["user", "reconfigure", "options"])
async def test_real_ha_form_json_serialization(flow, entry, step):
    """Use HA's actual HTTP form serializer, not only the internal flow manager."""
    import json

    from homeassistant.helpers.data_entry_flow import FlowManagerIndexView

    if step == "reconfigure":
        flow.context = {"source": "reconfigure", "entry_id": entry.entry_id}
        result = await flow.async_step_reconfigure()
    elif step == "options":
        options = HoneywellConfigFlow.async_get_options_flow(entry)
        options.hass = flow.hass
        options.handler = entry.entry_id
        result = await options.async_step_init()
    else:
        result = await flow.async_step_user()
    serialized = FlowManagerIndexView(None)._prepare_result_json(result)
    assert isinstance(serialized["data_schema"], list)
    assert serialized["data_schema"]
    json.dumps(serialized)


@pytest.mark.parametrize("step", ["user", "reconfigure"])
@pytest.mark.parametrize("host", ["", "https://device/", "host name", "meter:8000"])
async def test_invalid_host_is_a_serializable_field_error(flow, entry, step, host):
    import json

    from homeassistant.helpers.data_entry_flow import FlowManagerIndexView

    if step == "reconfigure":
        flow.context = {"source": "reconfigure", "entry_id": entry.entry_id}
    with patch(
        "custom_components.honeywell_mbus.config_flow.validate_connection", AsyncMock()
    ) as probe:
        result = await getattr(flow, f"async_step_{step}")({"host": host})
    probe.assert_not_awaited()
    assert result["errors"] == {"host": "invalid_host"}
    json.dumps(FlowManagerIndexView(None)._prepare_result_json(result))

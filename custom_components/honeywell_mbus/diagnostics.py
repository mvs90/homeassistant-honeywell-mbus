"""Diagnostics without network identifiers, serials or raw telegrams."""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import HoneywellConfigEntry
from .const import CONF_SERIAL


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HoneywellConfigEntry
) -> dict:
    coordinator = entry.runtime_data
    sample = coordinator.data
    meter = sample.reading
    return {
        "config": async_redact_data(dict(entry.data), {CONF_HOST, CONF_SERIAL}),
        "options": dict(entry.options),
        "connection_healthy": coordinator.last_update_success,
        "profile": {
            "manufacturer": meter.manufacturer_code,
            "model": "EEM400C-D-M",
            "device_version_byte": meter.device_version,
            "power_resolution_w": meter.power_resolution,
            "energy_resolution_kwh": float(meter.energy_resolution),
            "ct_ratio": meter.ct_ratio,
            "mbus_status": meter.status,
        },
        "transport": {"duration_seconds": sample.duration, "attempts": sample.attempts},
    }

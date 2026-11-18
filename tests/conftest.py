"""Local HA fixtures and a loopback-only M-Bus TCP emulator."""

import asyncio
from collections import deque
from pathlib import Path
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry, device_registry, entity_registry
from homeassistant.helpers import frame as frame_helper

from custom_components.honeywell_mbus.const import DOMAIN


@pytest.fixture
def frame():
    return bytes.fromhex((Path(__file__).parent / "fixtures/eem400c_v15.hex").read_text())


@pytest.fixture
async def hass(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    loader.async_setup(hass)
    frame_helper.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    device_registry.async_setup(hass)
    await area_registry.async_load(hass, load_empty=True)
    await device_registry.async_load(hass, load_empty=True)
    await entity_registry.async_load(hass, load_empty=True)
    component = tmp_path / "custom_components"
    component.mkdir()
    (component / DOMAIN).symlink_to(
        Path(__file__).parents[1] / "custom_components" / DOMAIN, target_is_directory=True
    )
    yield hass
    await hass.async_stop()


def make_entry(**overrides):
    defaults = dict(
        domain=DOMAIN,
        title="EEM400C-D-M",
        version=1,
        minor_version=1,
        data={
            "host": "meter.invalid",
            "port": 8000,
            "primary_address": 1,
            "serial_number": "12345678",
        },
        options={},
        source="user",
        unique_id="hon_eem400c_d_m_12345678",
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
        state=ConfigEntryState.SETUP_IN_PROGRESS,
    )
    defaults.update(overrides)
    return ConfigEntry(**defaults)


@pytest.fixture
async def entry(hass):
    entry = make_entry()
    with patch.object(hass.config_entries, "async_setup", AsyncMock(return_value=True)):
        await hass.config_entries.async_add(entry)
    return entry


class MeterServer:
    def __init__(self, frame):
        self.frame = frame
        self.counter = 16
        self.requests = []
        self.connections = 0
        self.faults = deque()
        self.writers = set()
        self.tasks = set()
        self.port = None

    async def handle(self, reader, writer):
        self.connections += 1
        self.writers.add(writer)
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            while True:
                request = await reader.readexactly(5)
                self.requests.append(request)
                assert request in [bytes.fromhex("105b015c16"), bytes.fromhex("107b017c16")]
                fault = self.faults.popleft() if self.faults else None
                if fault == "timeout":
                    continue
                if fault == "disconnect":
                    return
                data = bytearray(self.frame)
                if fault != "stale":
                    self.counter = (self.counter + 1) % 256
                data[15] = self.counter
                if fault == "unsupported":
                    data[13] = 0x16
                if fault == "identity":
                    data[7:11] = b"\x11\x11\x11\x11"
                if fault == "lower_energy":
                    data[22:26] = bytes.fromhex("44230100")
                data[-2] = sum(data[4:-2]) & 255
                if fault == "checksum":
                    data[-2] ^= 1
                if fault == "header":
                    data[0] = 0x10
                if fault == "partial":
                    writer.write(data[:12])
                    await writer.drain()
                    return
                if fault == "split":
                    for byte in data:
                        writer.write(bytes([byte]))
                        await writer.drain()
                        await asyncio.sleep(0)
                else:
                    writer.write(data)
                    await writer.drain()
        except asyncio.IncompleteReadError, ConnectionError:
            pass
        finally:
            self.writers.discard(writer)
            writer.close()
            await writer.wait_closed()
            self.tasks.discard(task)


@pytest.fixture
async def meter_server(frame):
    peer = MeterServer(frame)
    server = await asyncio.start_server(peer.handle, "127.0.0.1", 0)
    peer.port = server.sockets[0].getsockname()[1]
    yield peer
    server.close()
    await server.wait_closed()
    for writer in list(peer.writers):
        writer.close()
    if peer.tasks:
        await asyncio.gather(*list(peer.tasks), return_exceptions=True)

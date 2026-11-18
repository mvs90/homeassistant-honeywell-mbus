"""Parser tests and real asyncio TCP transport tests, all on loopback."""

import asyncio
from decimal import Decimal

import pytest

from custom_components.honeywell_mbus.api import (
    FrameError,
    HoneywellMbusClient,
    IdentityError,
    MeterStatusError,
    TransportError,
    UnsupportedMeterError,
    decode_frame,
    request_frame,
)


def mutate(frame, offset, value):
    data = bytearray(frame)
    data[offset : offset + len(value)] = value
    data[-2] = sum(data[4:-2]) & 255
    return bytes(data)


def test_real_layout_with_synthetic_identity(frame):
    reading = decode_frame(frame, 1)
    assert reading.serial == "12345678"
    assert reading.unique_id == "hon_eem400c_d_m_12345678"
    assert reading.energy == Decimal("1234.5")
    assert reading.energy_t1 == reading.energy and reading.energy_t2 == 0
    assert reading.energy_resolution == Decimal("0.1")
    assert reading.power == 200 and reading.power_resolution == 100
    assert reading.phases[0].voltage == 230 and reading.phases[0].current == Decimal("1.3")
    assert reading.ct_ratio == 1 and len(reading.phases) == 3
    assert not hasattr(reading, "partial_energy")


@pytest.mark.parametrize(
    ("offset", "value", "error"),
    [
        (0, b"\0", FrameError),
        (1, b"\x91", FrameError),
        (4, b"\x09", FrameError),
        (5, b"\x02", FrameError),
        (6, b"\x73", FrameError),
        (7, b"\xfa", FrameError),
        (11, b"\xef", UnsupportedMeterError),
        (13, b"\x16", UnsupportedMeterError),
        (14, b"\x03", UnsupportedMeterError),
        (16, b"\x01", MeterStatusError),
        (17, b"\x01", FrameError),
        (19, b"\x01", UnsupportedMeterError),
        (21, b"\x06", UnsupportedMeterError),
        (35, b"\x04", FrameError),
        (49, b"\xc8", UnsupportedMeterError),
        (52, (501).to_bytes(2, "little"), FrameError),
        (54, b"\x01", UnsupportedMeterError),
        (56, b"\xda", UnsupportedMeterError),
        (57, b"\x00", UnsupportedMeterError),
        (59, (30000).to_bytes(2, "little"), FrameError),
        (62, b"\xae", UnsupportedMeterError),
        (65, b"\0\x80", FrameError),
        (128, b"\x01", UnsupportedMeterError),
        (131, b"\0\0", FrameError),
        (131, (301).to_bytes(2, "little"), FrameError),
        (134, b"\xae", UnsupportedMeterError),
        (136, b"\x01", UnsupportedMeterError),
        (137, (1000).to_bytes(2, "little"), FrameError),
        (146, b"\x02", UnsupportedMeterError),
        (149, b"\x05", FrameError),
    ],
)
def test_rejects_invalid_records(frame, offset, value, error):
    with pytest.raises(error):
        decode_frame(mutate(frame, offset, value), 1)


@pytest.mark.parametrize("bad", [b"", b"\xe5", b"\0" * 151, b"\0" * 153])
def test_invalid_length(bad):
    with pytest.raises(FrameError):
        decode_frame(bad, 1)


def test_checksum(frame):
    data = bytearray(frame)
    data[-2] ^= 1
    with pytest.raises(FrameError, match="checksum"):
        decode_frame(data, 1)


def test_vif_scaling(frame):
    data = bytearray(frame)
    for offset in (21, 28, 35, 42):
        data[offset] = 4
    for offset in (62, 69, 89, 96, 116, 123, 134, 141):
        data[offset] = 0xAC
    data[-2] = sum(data[4:-2]) & 255
    reading = decode_frame(bytes(data), 1)
    assert reading.energy == Decimal("123.45") and reading.energy_resolution == Decimal("0.01")
    assert reading.power == 20 and reading.power_resolution == 10
    reading = decode_frame(mutate(frame, 56, b"\xdc"), 1)
    assert reading.phases[0].current == 13


def test_signed_power_not_installation_specific(frame):
    data = mutate(
        mutate(frame, 65, (-2).to_bytes(2, "little", signed=True)),
        137,
        (-2).to_bytes(2, "little", signed=True),
    )
    assert decode_frame(data, 1).power == -200


@pytest.mark.parametrize("address", [-1, 251, 254, 255, True, "2", 1.5])
def test_no_broadcast_or_invalid_address(address):
    with pytest.raises(ValueError):
        request_frame(address)


@pytest.mark.parametrize("control", [0x40, 0x43, 0x53, 0xFF])
def test_no_write_or_reset_controls(control):
    with pytest.raises(ValueError):
        request_frame(1, control)


def test_controls():
    assert request_frame(1) == bytes.fromhex("105b015c16")
    assert request_frame(1, 0x7B) == bytes.fromhex("107b017c16")


@pytest.mark.parametrize(
    ("port", "timeout", "gap"), [(0, 1, 0), (65536, 1, 0), (1, 0, 0), (1, 31, 0), (1, 1, -1)]
)
def test_invalid_connection_options(port, timeout, gap):
    with pytest.raises(ValueError):
        HoneywellMbusClient("localhost", port, 1, timeout=timeout, initial_gap=gap)


async def test_persistent_fragmented_and_concurrent_reads(meter_server):
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, initial_gap=0)
    meter_server.faults.extend(["split", "split"])
    try:
        first = await client.async_read()
        following = await asyncio.gather(*(client.async_read() for _ in range(8)))
        assert meter_server.connections == 1
        assert len(meter_server.requests) == 10
        assert len({x.reading.access_counter for x in [first, *following]}) == 9
        assert all(x.reading.serial == "12345678" for x in following)
        assert [x[1] for x in meter_server.requests] == [0x5B, 0x7B] * 5
    finally:
        await client.async_close()


@pytest.mark.parametrize(
    "fault", ["timeout", "disconnect", "partial", "checksum", "header", "stale"]
)
async def test_bounded_reconnect(meter_server, fault):
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, timeout=0.15, initial_gap=0)
    try:
        await client.async_read()
        meter_server.faults.append(fault)
        sample = await client.async_read()
        assert sample.attempts == 2 and sample.reading.energy == Decimal("1234.5")
        assert meter_server.connections == 2
    finally:
        await client.async_close()


async def test_counter_wrap(meter_server):
    meter_server.counter = 253
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, initial_gap=0)
    try:
        assert (await client.async_read()).reading.access_counter == 255
        assert (await client.async_read()).reading.access_counter == 0
    finally:
        await client.async_close()


@pytest.mark.parametrize("fault", ["timeout", "checksum", "stale"])
async def test_two_failures_raise_without_zero(meter_server, fault):
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, timeout=0.15, initial_gap=0)
    try:
        await client.async_read()
        meter_server.faults.extend([fault, fault])
        with pytest.raises((TransportError, FrameError)):
            await client.async_read()
        assert (await client.async_read()).reading.power == 200
    finally:
        await client.async_close()


@pytest.mark.parametrize(
    ("fault", "error"), [("unsupported", UnsupportedMeterError), ("identity", IdentityError)]
)
async def test_identity_and_profile_errors_do_not_retry(meter_server, fault, error):
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, initial_gap=0)
    try:
        await client.async_read()
        n = len(meter_server.requests)
        meter_server.faults.append(fault)
        with pytest.raises(error):
            await client.async_read()
        assert len(meter_server.requests) == n + 1
    finally:
        await client.async_close()


async def test_identity_changes_during_initial_validation(meter_server):
    meter_server.faults.extend([None, "identity"])
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, initial_gap=0)
    try:
        with pytest.raises(IdentityError):
            await client.async_read()
    finally:
        await client.async_close()


async def test_stale_initial_validation(meter_server):
    meter_server.faults.extend([None, "stale", None, "stale"])
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, initial_gap=0)
    try:
        with pytest.raises(FrameError, match="initial"):
            await client.async_read()
    finally:
        await client.async_close()


async def test_cancel_and_close_release_pending_transport(meter_server):
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, timeout=5, initial_gap=0)
    await client.async_read()
    meter_server.faults.append("timeout")
    task = asyncio.create_task(client.async_read())
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await client.async_close()
    await client.async_close()
    with pytest.raises(TransportError, match="closed"):
        await client.async_read()


async def test_close_interrupts_pending_read(meter_server):
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, timeout=5, initial_gap=0)
    await client.async_read()
    meter_server.faults.append("timeout")
    task = asyncio.create_task(client.async_read())
    await asyncio.sleep(0.02)
    await client.async_close()
    with pytest.raises(TransportError):
        await asyncio.wait_for(task, 0.5)


async def test_decreasing_energy_is_not_published_and_recovers(meter_server):
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, initial_gap=0)
    try:
        await client.async_read()
        meter_server.faults.extend(["lower_energy", "lower_energy"])
        with pytest.raises(FrameError, match="Energy total decreased"):
            await client.async_read()
        assert (await client.async_read()).reading.energy == Decimal("1234.5")
    finally:
        await client.async_close()


async def test_decreasing_energy_during_initial_validation(meter_server):
    client = HoneywellMbusClient("127.0.0.1", meter_server.port, 1, initial_gap=0)
    meter_server.faults.extend([None, "lower_energy", None, "lower_energy"])
    try:
        with pytest.raises(FrameError, match="Energy total decreased"):
            await client.async_read()
    finally:
        await client.async_close()

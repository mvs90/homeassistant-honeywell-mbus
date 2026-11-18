"""Async, read-only wired M-Bus API for the supported Honeywell profile.

No Home Assistant imports, filesystem writes, management credentials or MQTT.
Only REQ_UD2 telegrams are generated. The TCP gateway owns the UART settings.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal


class MbusError(Exception):
    """Base error safe to display without frames or network identifiers."""


class TransportError(MbusError):
    """The gateway did not provide a complete reply."""


class FrameError(MbusError):
    """An invalid or stale reply was received."""


class UnsupportedMeterError(MbusError):
    """The model or record layout is not supported."""


class IdentityError(MbusError):
    """A configured endpoint now answers for a different meter."""


class MeterStatusError(MbusError):
    """The meter reports a nonzero status."""


@dataclass(frozen=True, slots=True)
class PhaseReading:
    """Measurements for one phase, in V, A, W and var."""

    voltage: Decimal
    current: Decimal
    power: int
    reactive_power: int


@dataclass(frozen=True, slots=True)
class MeterReading:
    """Decoded values; resettable partial counters are deliberately excluded."""

    serial: str
    manufacturer_code: str
    device_version: int
    status: int
    access_counter: int
    energy: Decimal
    energy_t1: Decimal
    energy_t2: Decimal
    energy_resolution: Decimal
    power: int
    power_resolution: int
    reactive_power: int
    phases: tuple[PhaseReading, ...]
    ct_ratio: int
    tariff: int

    @property
    def unique_id(self) -> str:
        """A device identity independent of gateway IP, port and primary address."""
        return f"{self.manufacturer_code.lower()}_eem400c_d_m_{self.serial}"


@dataclass(frozen=True, slots=True)
class MeterSample:
    """A verified fresh sample with transport diagnostics."""

    reading: MeterReading
    received_at: datetime
    duration: float
    attempts: int


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FrameError(message)


def _bcd(data: bytes) -> int:
    _require(all((byte & 15) < 10 and byte >> 4 < 10 for byte in data), "Invalid BCD value")
    return sum(((byte >> 4) * 10 + (byte & 15)) * 100**index for index, byte in enumerate(data))


def request_frame(address: int, control: int = 0x5B) -> bytes:
    """Generate only an addressed REQ_UD2; reject broadcast/write controls."""
    if isinstance(address, bool) or not isinstance(address, int) or not 0 <= address <= 250:
        raise ValueError("Primary address must be an integer from 0 to 250")
    if control not in (0x5B, 0x7B):
        raise ValueError("Only REQ_UD2 is supported")
    return bytes((0x10, control, address, (control + address) & 255, 0x16))


def decode_frame(frame: bytes, address: int) -> MeterReading:
    """Decode the captured HON/0x15 profile using the actual VIF units.

    This is intentionally a model-specific parser, not a generic M-Bus decoder.
    Unsupported profiles fail closed, rather than inventing scaled readings.
    """
    _require(len(frame) == 152, "Unexpected frame size")
    _require(frame[:4] == b"\x68\x92\x92\x68" and frame[-1] == 0x16, "Invalid frame header")
    _require(sum(frame[4:-2]) & 255 == frame[-2], "Invalid checksum")
    _require(
        frame[4] in (0x08, 0x28) and frame[5] == address and frame[6] == 0x72,
        "Unexpected reply type or address",
    )
    serial = f"{_bcd(frame[7:11]):08d}"
    if frame[11:13] != b"\xee\x21" or frame[13] != 0x15 or frame[14] != 2:
        raise UnsupportedMeterError("Unsupported manufacturer, version or medium")
    if frame[16]:
        raise MeterStatusError("Meter reports a nonzero M-Bus status")
    _require(frame[17:19] == b"\0\0", "Unexpected signature")

    def expect(offset: int, value: bytes) -> None:
        if frame[offset : offset + len(value)] != value:
            raise UnsupportedMeterError("Unsupported record layout")

    def uint16(offset: int) -> int:
        return int.from_bytes(frame[offset : offset + 2], "little")

    def energy(offset: int, dife: int) -> tuple[Decimal, Decimal]:
        expect(offset, bytes((0x8C, dife)))
        vif = frame[offset + 2]
        if vif not in (4, 5):
            raise UnsupportedMeterError("Unsupported energy VIF")
        resolution = Decimal(10) ** (vif - 6)
        return Decimal(_bcd(frame[offset + 3 : offset + 7])) * resolution, resolution

    def power(offset: int, reactive: bool, phase: int) -> tuple[int, int]:
        prefix = b"\x82\x40" if reactive else b"\x02"
        expect(offset, prefix)
        position = offset + len(prefix)
        vif = frame[position]
        if vif not in (0xAC, 0xAD):
            raise UnsupportedMeterError("Unsupported power VIF")
        expect(position + 1, bytes((0xFF, phase)))
        resolution = 10 ** ((vif & 0x7F) - 0x2B)
        raw = int.from_bytes(frame[position + 3 : position + 5], "little", signed=True)
        _require(raw != -32768, "Invalid power sentinel")
        return raw * resolution, resolution

    t1, resolution = energy(19, 0x10)
    energy(26, 0x11)  # Validate but never expose the resettable partial counter.
    t2, resolution_t2 = energy(33, 0x20)
    energy(40, 0x21)
    _require(resolution == resolution_t2, "Inconsistent energy resolution")
    phases: list[PhaseReading] = []
    for phase in (1, 2, 3):
        base = 47 + (phase - 1) * 27
        expect(base, bytes((2, 0xFD, 0xC9, 0xFF, phase)))
        voltage = Decimal(uint16(base + 5))
        _require(voltage <= 500, "Invalid voltage")
        expect(base + 7, b"\x02\xfd")
        vif = frame[base + 9]
        if vif not in (0xDB, 0xDC):
            raise UnsupportedMeterError("Unsupported current VIF")
        expect(base + 10, bytes((0xFF, phase)))
        current = Decimal(uint16(base + 12)) * (Decimal("0.1") if vif == 0xDB else 1)
        _require(current <= 2000, "Invalid current")
        watts, _ = power(base + 14, False, phase)
        reactive, _ = power(base + 20, True, phase)
        phases.append(PhaseReading(voltage, current, watts, reactive))
    expect(128, b"\x02\xff\x68")
    ct_ratio = uint16(131)
    _require(1 <= ct_ratio <= 300, "Invalid transformer ratio")
    watts, power_resolution = power(133, False, 0)
    reactive, _ = power(139, True, 0)
    expect(146, b"\x01\xff\x13")
    tariff = frame[149]
    _require(tariff in (0, 4), "Unsupported tariff")
    # Signed power is retained. Installation-specific assumptions (UV has no PV)
    # must not be hardcoded into a reusable public integration.
    _require(
        abs(sum(phase.power for phase in phases) - watts) <= 4 * power_resolution,
        "Inconsistent phase power",
    )
    return MeterReading(
        serial,
        "HON",
        frame[13],
        frame[16],
        frame[15],
        t1 + t2,
        t1,
        t2,
        resolution,
        watts,
        power_resolution,
        reactive,
        tuple(phases),
        ct_ratio,
        tariff,
    )


class HoneywellMbusClient:
    """One async TCP reader, one primary address, with bounded reconnects.

    The persistent socket and lock prevent overlapping requests. No constructor
    side effects: all I/O happens in async_read or async_close. Call async_close
    during unload or cancellation. UART/baud changes are deliberately excluded.
    """

    def __init__(
        self,
        host: str,
        port: int,
        address: int,
        *,
        timeout: float = 1.5,
        expected_serial: str | None = None,
        initial_gap: float = 1.3,
    ) -> None:
        request_frame(address)
        if not 1 <= port <= 65535 or not 0.1 <= timeout <= 30 or initial_gap < 0:
            raise ValueError("Invalid connection settings")
        self.host = host
        self.port = port
        self.address = address
        self.timeout = timeout
        self.expected_serial = expected_serial
        self._initial_gap = initial_gap
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._control = 0x5B
        self._previous_counter: int | None = None
        self._previous_energy: Decimal | None = None
        self._closed = False

    async def _disconnect(self) -> None:
        writer, self._writer = self._writer, None
        self._reader = None
        if writer is not None:
            writer.close()
            try:
                async with asyncio.timeout(1):
                    await writer.wait_closed()
            except TimeoutError, OSError:
                pass

    async def async_close(self) -> None:
        """Close permanently, also interrupting a pending read promptly."""
        self._closed = True
        await self._disconnect()

    async def _exchange(self) -> MeterReading:
        if self._closed:
            raise TransportError("Client is closed")
        try:
            async with asyncio.timeout(self.timeout):
                if self._writer is None or self._writer.is_closing():
                    self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
                reader, writer = self._reader, self._writer
                assert reader is not None
                writer.write(request_frame(self.address, self._control))
                await writer.drain()
                header = await reader.readexactly(4)
                _require(
                    header[0] == header[3] == 0x68
                    and header[1] == header[2]
                    and 3 <= header[1] <= 255,
                    "Invalid stream header",
                )
                frame = header + await reader.readexactly(header[1] + 2)
                value = decode_frame(frame, self.address)
                if self.expected_serial is not None and value.serial != self.expected_serial:
                    raise IdentityError("The endpoint now answers for another meter")
                self._control = 0x7B if self._control == 0x5B else 0x5B
                return value
        except asyncio.CancelledError:
            await self._disconnect()
            raise
        except (TimeoutError, OSError, asyncio.IncompleteReadError) as error:
            await self._disconnect()
            raise TransportError("Gateway timeout or incomplete response") from error
        except MbusError:
            await self._disconnect()
            raise

    async def async_read(self) -> MeterSample:
        """Return a fresh sample; never turn invalid/missing data into zero."""
        async with self._lock:
            started = time.monotonic()
            for attempt in (1, 2):
                try:
                    reading = await self._exchange()
                    if self._previous_counter is None:
                        first = reading
                        await asyncio.sleep(self._initial_gap)
                        reading = await self._exchange()
                        if reading.serial != first.serial:
                            raise IdentityError("Meter identity changed during validation")
                        _require(
                            reading.access_counter != first.access_counter, "Stale initial response"
                        )
                        _require(reading.energy >= first.energy, "Energy total decreased")
                    else:
                        _require(reading.access_counter != self._previous_counter, "Stale response")
                    if self._previous_energy is not None:
                        _require(reading.energy >= self._previous_energy, "Energy total decreased")
                    self.expected_serial = reading.serial
                    self._previous_counter = reading.access_counter
                    self._previous_energy = reading.energy
                    return MeterSample(
                        reading, datetime.now(UTC), time.monotonic() - started, attempt
                    )
                except asyncio.CancelledError:
                    await self._disconnect()
                    raise
                except TransportError, FrameError:
                    await self._disconnect()
                    if attempt == 2 or self._closed:
                        raise
                    await asyncio.sleep(0.05)
                except MbusError:
                    await self._disconnect()
                    raise
        raise AssertionError("Unreachable retry state")

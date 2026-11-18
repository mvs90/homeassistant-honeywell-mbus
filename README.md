# Honeywell M-Bus for Home Assistant

Native, asynchronous wired M-Bus readings from a **Honeywell EEM400C-D-M** through
a transparent TCP-to-serial bridge, such as **W&T Com-Server++ → RS232 → Relay PW20**.
No MQTT broker, shell command, add-on or gateway management password is required.

**Development preview, version 0.1.0.** Prepared for installation as a HACS custom
repository. **Not submitted to or included in the HACS default store.** Local
protocol/emulator and Home Assistant tests do not replace a supervised hardware
acceptance test. This version has not replaced an existing production reader.

[Deutsche Anleitung](docs/DE.md) · [Migration](docs/MIGRATION.md) ·
[HACS readiness](docs/HACS_SUBMISSION.md) · [Protocol scope](docs/PROTOCOL.md)

## Supported devices and API

The API speaks **wired M-Bus (EN 13757) over raw TCP**, not Modbus or a REST API.
Only the captured **HON / device-version byte 0x15 / electrical medium / 152-byte
EEM400C-D-M profile** is supported initially. Other firmware or meter models are
rejected until an anonymized telegram and tests establish compatibility.

W&T/PW20 is the reference hardware chain. Other transparent serial bridges may
work but are not claimed as hardware-tested. The bridge must already be configured
for **8E1, no handshake**, with the same baud rate as the meter. The PW20 and this
meter support up to 9600 baud; long wiring may require a lower rate. The integration
does not alter UART settings, addresses, tariffs, counters or gateway firmware.

One meter/primary address per TCP bridge is supported in this first version.
Only one application may read a physical M-Bus at a time. Stop legacy readers
before setting up the native integration; never run this alongside another master.
There is no automatic bus scan, broadcast or secondary-address selection.

## Features

- UI setup, options and same-meter endpoint reconfiguration.
- Persistent, nonblocking TCP connection with serialized requests and bounded retries.
- Checksums, model/profile, BCD, actual VIF scales, status, identity and fresh counters.
- No invented zero values on failure: entities become unavailable and recover.
- Stable device and entity identifiers independent of gateway IP and primary address.
- Redacted downloadable diagnostics; no raw frames, hostnames or serial numbers.
- English and German UI translations and bundled custom integration icons.

### Sensors

| Measurements | Unit | Enabled by default |
| --- | --- | --- |
| Total active power | W | Yes |
| Cumulative energy (T1 + T2; no resettable partial counters) | kWh | Yes |
| Total reactive power | var | Yes |
| Voltage, current, active/reactive power for L1, L2, L3 | V, A, W, var | Yes |
| Current-transformer ratio, M-Bus status | — | Yes, diagnostics |
| Last successful read, read duration, read attempts | timestamp, s, — | No, diagnostics |

This gives **17 default sensors and 3 optional diagnostics**. Cumulative energy
uses `total_increasing` and can be selected in the Energy dashboard. Power retains
its sign. Units and resolutions come from each telegram: the supported profile
may report **10 or 100 W** and **0.01 or 0.1 kWh** steps. Polling faster does not
improve physical resolution. Transformer scaling is not applied a second time.
The device-version byte is not presented as a firmware version.

## Installation

Requires Home Assistant **2026.11.0 or later**.

1. In HACS, add `https://github.com/mvs90/homeassistant-honeywell-mbus` as a
   **custom repository**, category **Integration**, then download it. Alternatively,
   copy `custom_components/honeywell_mbus` into your HA `custom_components` folder.
2. Restart Home Assistant to discover the newly installed custom integration.
3. Stop any previous reader on the same bus.
4. Add **Honeywell M-Bus** under **Settings → Devices & services → Add integration**.
5. Enter the bridge host/IP, its raw TCP data port (commonly **8000**) and the meter's
   primary address (**0–250**). Do not use a W&T management/control port.

The flow validates two fresh responses before creating a config entry and always
closes its temporary connection. A different meter cannot silently take over an
existing entry. Configure a replacement meter separately.

## Options and update behavior

- Polling interval: **2 seconds** by default; configurable from 1 to 3600 seconds.
- Per-response/connect timeout: **1.5 seconds** by default; 0.5–30 seconds.
- At most two attempts per refresh. Initial identity/freshness validation uses two
  telegrams separated by 1.3 seconds.

This is **local polling, not push**. The HA coordinator schedules serialized
refreshes; response time, initial validation and retries can extend the actual
cadence. Start at 2 seconds and increase it if the network, meter or serial wiring
cannot keep up. Reconnection and reload do not write a polling cache to disk.

## Troubleshooting

- **Cannot connect:** check host, raw data port, primary address, power and UART
  parameters. Stop any other bus reader. A working web UI does not prove that the
  raw serial port works.
- **Unsupported meter:** provide an anonymized telegram/profile in an issue.
  Do not force a multiplier intended for a different firmware.
- **Wrong meter:** verify wiring and serial identity; reconfiguration deliberately
  cannot attach an existing energy history to another meter.
- **Coarse power steps or no change:** observe the VIF resolution. A faster poll
  cannot create extra precision or force a meter to measure more often.
- **Unavailable:** no valid fresh reply was accepted. Existing values are not
  published as zero. Polling continues with bounded retry/reconnect behavior.
- **History:** follow the staged [migration procedure](docs/MIGRATION.md). Removing
  this integration must not be accompanied by deleting Recorder statistics.

## Removal

Remove the config entry under Devices & services, then uninstall the files through
HACS if desired. The socket and coordinator close on unload. Removing a config entry
does not execute physical actions or purge Recorder/InfluxDB data. Review Energy
dashboard sources separately if you no longer want the sensor selected there.

## Development

```sh
python3.14 -m venv .venv
.venv/bin/pip install 'homeassistant==2026.11.0' -r requirements-test.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest --cov --cov-report=term-missing
```

All TCP tests bind only to `127.0.0.1` on an ephemeral port. Tests never contact a
real gateway or require secrets. The fixture uses a synthetic serial and energy
total. CI runs tests, Ruff, hassfest and the HACS repository validator. Validators
do not submit the repository to the default store.

## References and affiliation

- [Honeywell EEM400C-D-M M-Bus data sheet](https://sbc-support.com/uploads/tx_srcproducts/26-589_GER_DS_HON_EEM400C-D-M_M-Bus.pdf)
- [Relay PW20 specifications](https://service.relay.de/media/manuals/MR006DE.pdf)
- [W&T Com-Server manual](https://www.wut.de/download/manual/e-5866w-10-prde-220.pdf)

An independent community integration; not an official Honeywell, Relay, W&T or
Home Assistant product. Original project icon; no vendor or Home Assistant logo.

# Verification — 2026-11-18

Environment: macOS arm64, Python 3.14.6, Home Assistant 2026.11.0.

- **139 tests passed**.
- **98.68% combined statement/branch coverage**, with a 95% minimum enforced.
- Ruff lint and formatting checks pass.
- One deprecation warning originates in HA's HTTP application dependency, outside
  this integration. There are no integration test failures.

## What was verified

- Captured record layout with a synthetic identity and energy total; actual VIF
  scaling, BCD validation, status/profile/identity errors and signed power.
- Rejection of broadcast/write/reset controls, malformed frames and unsupported
  profile variants. Current-transformer scaling is not applied twice.
- Real asyncio loopback TCP server: fragmented replies, persistent reuse,
  serialized concurrent requests, reconnects, timeouts, partial frames, stale
  replies, access-counter rollover, cancellation and prompt close.
- Decreasing energy totals are rejected during initial validation and subsequent
  reads. A valid later sample recovers without publishing a fabricated zero.
- HA’s actual HTTP form serializer for setup, reconfiguration, options and malformed-host errors.
- Native HA config manager, UI validation, duplicate endpoint/serial protection,
  same-meter reconfiguration, options and redacted diagnostics.
- Native HA sensor platform and entity registry: 20 registered sensors, 17 enabled
  by default; correct energy state class; stable entity IDs across reload; options
  automatically reload the integration; successful unload closes the owned client.
- Complete translation keys, placeholders, sensor coverage and installable package metadata.
- Source-tree check for actual installation endpoints, original serials and
  credentials before publication.

## Limits of this verification

The automated suite uses a synthetic identity, loopback TCP and local HA. It
never contacts a real gateway or switches devices. Separate exclusive hardware
acceptance and deployment are recorded after their completion. A short acceptance
test cannot establish long-term reliability. HACS default-store acceptance is not
implied.

CI also targets Home Assistant 2026.11.1 and 2026.11.2 on Linux, plus hassfest and the official
HACS repository validator. Consult actual GitHub workflow results for their status.

## Exclusive real-hardware acceptance

On 2026-11-18 the native API completed 18 valid reads on the reference
W&T Com-Server++ → Relay PW20 → Honeywell EEM400C-D-M chain at 9600 baud,
8E1. The legacy reader was stopped throughout the test and restored afterward.
Steady reads took approximately 0.20 seconds. One refresh required the bounded
second attempt and recovered automatically. Initial two-reply validation took
approximately 1.72 seconds; all accepted totals and identities were consistent.
No physical switching or meter/gateway configuration commands were sent.
This establishes short acceptance, not long-term reliability.

## Native production acceptance on HA 2026.11.1

- Actual HTTP setup, options and reconfiguration forms serialize successfully.
  Malformed hosts produce a translated field error without a bus connection.
- Exclusive MQTT-to-native cutover retained all 17 previous measurement entity IDs
  and their units/classes. Original statistics were checked across 15 statistic
  IDs and 435 historical rows; the historical response was identical. Energy
  dashboard preferences were unchanged.
- Reloading the integration kept all 20 registered entity IDs and resumed reads.
- Normal replies were approximately 0.20 seconds. On the reference HA installation,
  the response allowance was increased to 3 seconds after transient transport
  timeouts; the scan interval remains 2 seconds. The default timeout remains
  configurable. Increasing its allowance does not delay a healthy response.
  After this tuning, all 26 subsequent cached-diagnostics observations were
  healthy and showed ongoing refreshes.

These checks do not prove uninterrupted operation over days, recovery from every
host/storage fault, or compatibility with other meter profiles.

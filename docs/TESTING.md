# Initial local verification — 2026-11-18

Environment: macOS arm64, Python 3.14.6, Home Assistant 2026.11.0.

- **109 tests passed**.
- **98.65% combined statement/branch coverage**, with a 95% minimum enforced.
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
- Native HA config manager, UI validation, duplicate endpoint/serial protection,
  same-meter reconfiguration, options and redacted diagnostics.
- Native HA sensor platform and entity registry: 20 registered sensors, 17 enabled
  by default; correct energy state class; stable entity IDs across reload; options
  automatically reload the integration; successful unload closes the owned client.
- Source-tree check for actual installation endpoints, original serials and
  credentials before publication.

## Limits of this verification

No integration was installed on the production HA instance. No second reader was
connected to the real M-Bus and no physical commands were sent. A supervised real
hardware acceptance test, long-running reliability test and production/history
migration remain separate steps. HACS default-store acceptance is not implied.

CI also targets Home Assistant 2026.11.2 on Linux, plus hassfest and the official
HACS repository validator. Consult actual GitHub workflow results for their status.

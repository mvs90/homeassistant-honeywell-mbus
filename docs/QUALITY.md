# Home Assistant and HACS readiness

This is a custom integration. Passing validation does **not** assign an official
Home Assistant quality tier or mean inclusion in Core or the HACS default store.
The Core quality scale is used as a design checklist where applicable.

| Requirement / behavior | Implementation and evidence |
| --- | --- |
| HACS repository | Public repository, description, topics, MIT license, README, root `hacs.json`, one integration directory |
| Manifest | Version, code owner, documentation/issues links, config flow, device type, `local_polling` |
| Setup | UI only; validate the selected endpoint and two fresh replies before creating the entry |
| Unique device and entities | Meter identity; duplicate endpoint prevention; never derive identity from the host address |
| Runtime data | Typed `ConfigEntry` coordinator; persistent socket; no global per-entry cache |
| Async I/O | Standard-library async TCP client; no blocking reads, shell commands, MQTT or polling files |
| Parallel updates | One coordinator/client, request lock and `PARALLEL_UPDATES = 0` |
| Lifecycle | Close temporary flow probes, failed setup, cancellation, reload and unload |
| Errors and recovery | Bounded retries, availability and coordinator transition logs; reject identity and counter corruption |
| Entity metadata | Has-entity-name, device/state classes, physical units, diagnostic categories; optional diagnostics disabled initially |
| Energy | Lifetime T1+T2, `total_increasing`; no resettable partial counter; preserve units and sign |
| Localization | 18 complete UI/sensor locales, checked for equal keys and placeholders |
| Reconfiguration | Same meter only; options automatically reload the integration |
| Diagnostics | Redact host/serial, omit raw telegrams and credentials |
| Tests | Native HA flows/platform/registry/reload, real loopback TCP, parser faults, cancellation, metadata and translations; enforced coverage floor |
| Continuous validation | Ruff, pytest, hassfest, HACS validator on pushes/PRs |
| Documentation | Supported profile, installation/options, update behavior, troubleshooting, limitations, removal, examples and migration |
| Security | No management credentials or write telegrams; no exposed actions or listeners; no third-party runtime dependency |

Authentication/reauthentication, service-action exceptions, automatic discovery,
web sessions and multi-device discovery are not applicable to this read-only,
manually addressed raw TCP protocol. The gateway must already be configured.
The API is intentionally shipped with the custom integration; a future **Core**
submission would require a separately packaged library and the Core review process.

## Languages

English, German, French, Spanish, Italian, Dutch, Portuguese, Brazilian Portuguese,
Polish, Czech, Danish, Swedish, Norwegian Bokmål, Finnish, Ukrainian, Simplified
Chinese, Traditional Chinese and Japanese. Community language review is welcome;
translations do not imply hardware support for additional meter variants.

## Supported scope and remaining acceptance

Only the documented Honeywell EEM400C-D-M / HON / device-version-byte 0x15 profile
is supported. Do not broaden compatibility claims without anonymized fixtures.
Release acceptance includes real exclusive-bus polling, reload, value/unit checks
and an explicit production migration review. Long-term reliability is monitored
in operation and is not proved by a short test or by passing HACS validation.

References: [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/),
[HACS general requirements](https://www.hacs.xyz/docs/publish/start/),
[Home Assistant quality scale](https://contributors.home-assistant.io/core/quality-scale/),
[HA integration translations](https://contributors.home-assistant.io/core/integrations/translations/).

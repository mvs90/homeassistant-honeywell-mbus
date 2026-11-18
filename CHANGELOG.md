# Changelog

## 0.2.1

- Fix HA HTTP form serialization by separating host normalization from the UI schema.
- Report malformed hosts as a translated field error without contacting the bus.
- Exercise HA’s actual HTTP form serializer for setup, reconfiguration and options.

## 0.2.0

- Complete setup/options/errors/sensor translations in 18 languages.
- Explicit coordinator-only parallel update policy.
- Translation/placeholder/package-contract validation and HA 2026.11.1 CI coverage.
- HA/HACS quality checklist and production migration documentation.

## 0.1.0 — development preview

- Native async wired M-Bus TCP API for the validated Honeywell EEM400C-D-M profile.
- UI setup/options/reconfiguration, stable identities and native measurement sensors.
- Bounded retry/reconnection, freshness/identity checks and deterministic cleanup.
- Redacted diagnostics, English/German translations and local brand assets.
- Synthetic protocol fixtures, loopback TCP and Home Assistant lifecycle tests.
- HACS repository structure, validation workflows and staged migration documentation.

No production migration or HACS default-store submission in this preparation.

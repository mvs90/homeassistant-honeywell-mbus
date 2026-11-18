# HACS default-store submission checklist

This repository is being prepared for a **future** HACS default-store submission.
No submission, request for inclusion, brand-repository PR or public release is
performed as part of the initial local preparation.

## Prepared

- One integration under `custom_components/honeywell_mbus`.
- Manifest with version, local-polling class, config flow, code owner and issue links.
- Root `hacs.json`, README, MIT license, English/German UI and bundled brand assets.
- Config flow, options, same-meter reconfiguration, diagnostics and unload cleanup.
- Local synthetic-fixture, TCP emulator and native Home Assistant tests.
- CI for minimum/current tested HA versions, lint, hassfest and HACS validation.
- Supported-device scope, limitations, troubleshooting, removal and migration plan.
- GitHub description, searchable topics and issues enabled.

## Must be completed before submitting

- Supervised acceptance on the real meter/gateway, with the legacy reader stopped.
- Validate long-running polling/reconnects, an HA restart and integration reload on
  hardware. Preserve all original histories and verify migration separately.
- Collect additional anonymized firmware/model fixtures before widening support.
- Confirm all GitHub validation jobs pass and inspect warnings.
- Select a stable public release after hardware acceptance.
- Recheck [current HACS requirements](https://www.hacs.xyz/docs/publish/integration/)
  and [submission procedure](https://www.hacs.xyz/docs/publish/include/) at that time.
- Obtain explicit approval to submit. Passing validation does not mean acceptance
  or an official affiliation with Home Assistant or the hardware vendors.

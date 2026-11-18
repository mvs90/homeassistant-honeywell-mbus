# Staged migration from an existing MQTT reader

**Migration is an explicit deployment step, never an automatic install side effect.**
There is no automatic Recorder/statistics rewrite, MQTT deletion or entity-registry
takeover. A change from MQTT unique IDs to native integration unique IDs needs an
explicitly supervised migration. Do not run two readers against the same bus.

## Before changing the reader

1. Create and verify an HA configuration backup. Preserve Recorder/InfluxDB history.
2. Export the existing entity IDs, unique IDs, device metadata, labels, area,
   enabled/disabled flags, Energy dashboard references and automation/dashboard
   references. Record the current kWh total, unit and statistic ID.
3. Test this integration in a separate HA instance against the simulator first.
   Plan a short exclusive hardware acceptance window before final migration.
4. During that window, stop the legacy reader, ensure its current transaction has
   ended, then validate the native connection. Resume the legacy reader if testing
   fails. Never leave both polling the same gateway.

## Planned identity mapping

| Old measurement | New native measurement key |
| --- | --- |
| Total active power | `power` |
| Cumulative total energy | `energy` |
| Total reactive power | `reactive_power` |
| Phase voltage | `voltage_l1`, `voltage_l2`, `voltage_l3` |
| Phase current | `current_l1`, `current_l2`, `current_l3` |
| Phase active power | `power_l1`, `power_l2`, `power_l3` |
| Phase reactive power | `reactive_power_l1`, `reactive_power_l2`, `reactive_power_l3` |
| Transformer ratio / M-Bus status | `ct_ratio`, `mbus_status` |

The native unique IDs have the form `hon_eem400c_d_m_<serial>_<key>`. They are not
the legacy MQTT unique IDs. Device and entity IDs must not be assumed interchangeable.

## Controlled cutover

After hardware acceptance and approval for production cutover:

1. Stop the legacy writer and preserve its discovery configuration for rollback.
2. Remove only the old MQTT discovery/device entries once the registry mapping has
   been exported and checked. This may free their entity IDs. **Do not purge history
   or remove long-term statistics.** Do not clear unrelated MQTT topics.
3. Set up the native integration. Give each native sensor the corresponding previous
   entity ID after checking that the ID is available. Restore labels and area.
4. Check that native value, unit, device class and state class match the prior sensor.
   Confirm the same statistic ID and historic data are still usable; entity ID
   reuse alone is not proof that every external consumer has migrated.
5. Confirm all Energy dashboard, InfluxDB, automations, dashboards and Assist
   references against the exported mapping. Check current total continuity and
   absence of duplicate summation.
6. Keep rollback artifacts until several normal operating cycles succeed.

Do not merge the raw meter's lifetime total into an unrelated counter with a
different baseline. Do not turn missing readings into zero or sum duplicate meters.
Recorder history and InfluxDB series are separate; verify both explicitly.

### Existing Recorder target IDs

When a newly registered native sensor is renamed onto an existing historical
entity ID, Recorder can report that it cannot rename the temporary sensor’s
metadata because the target already exists. Do not delete the target history to
silence that message. Confirm the original statistic ID, units and historical
rows remain intact, and verify new samples continue on that ID. Temporary native
IDs must not be added as duplicate Energy sources.

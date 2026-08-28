# 1.2.4 (2026-08-24)

Small polish - no change to entity IDs or reported values.

- Dropped "sensor" from the integration's display title (Settings > Devices & Services), so it reads "Mold Risk Index" - matching manifest.json's name, which already omitted it.
- Added step-by-step README instructions for migrating from the upstream integration to this fork, confirmed to preserve entity IDs and history.

# 1.2.3 (2026-08-24)

Log warnings more helpfully, plus internal cleanup - no change to entity IDs, names, or reported values.

- Humidity readings outside 0-100% now log a warning naming the sensor, what it reported, and what it was clamped to, instead of being silently absorbed.
- The "non-numeric state" warning now names which sensor triggered it, matching the existing temperature-unit warning.
- Removed leftover code from the recent listener rewrite (unused constructor parameters, a redundant state reset) and consolidated the last of the duplicated limit-calculation formulas.
- Added a test suite and CI linting/formatting checks, so regressions get caught automatically going forward.

# 1.2.2 (2026-08-24)

⚡ Skip redundant work on every humidity update - no behavior change.

- 🎯 `Level 1/2/3 Limit` only depend on temperature, never humidity, so a humidity-only update no longer touches them at all.
- ✅ `Current Index` still updates exactly as before on every temperature or humidity change.
- 🔧 Internal only - no change to entity IDs, names, or reported values.

# 1.2.1 (2026-08-24)

Internal rewrite of how the Limit and Current Index sensors listen for source sensor updates: each entity used to register its own listener on the temperature/humidity sensors, so a config entry ended up with 4 separate listeners fanning into a shared calculator that deduplicated redundant recalculation by comparing state-change event object identity - a behavior that worked but wasn't guaranteed, and didn't cover entity setup at all. As a result, the "unsupported temperature unit" warning could log up to 4 times on every Home Assistant startup or reload for a single misconfigured sensor. Now a config entry registers exactly one listener per source sensor, updates a shared calculator once, and only writes state for the entities whose value actually changed. No change in entity IDs, names, or reported values.

# 1.2.0 (2026-08-24)

Split the `Limit` sensor into three entities, one per risk level: `Level 1 Limit`, `Level 2 Limit`, and `Level 3 Limit`, each reporting the humidity threshold for that level at the current temperature. Previously only level 1 was a real entity; levels 2 and 3 were only available as attributes on the `Limit` sensor, which meant they couldn't be graphed, tracked in statistics, or used directly in a `state` trigger. The old `Limit` sensor's entity ID is preserved as `Level 1 Limit`, so existing automations referencing it keep working. Also renamed the `Risk Index` sensor to `Current Index` for clarity now that there are multiple level-related entities.

# 1.1.3 (2026-08-24)

Restrict the temperature and humidity sensor pickers in the setup/options flow to entities that declare the matching `device_class` (`temperature` / `humidity`). Previously any `sensor.*` entity could be selected for either field, so it was possible to accidentally configure, say, a humidity sensor as the temperature input with no warning.

# 1.1.2 (2026-08-24)

Require a recognized temperature unit (Celsius, Fahrenheit, or Kelvin) on the configured temperature sensor. Previously, a sensor with no unit set was silently assumed to already be Celsius; that assumption could itself produce a wrong risk calculation if the sensor was actually reporting Fahrenheit or Kelvin without declaring it. The risk sensors now go to `unknown` and log a warning in that case, rather than guessing.

# 1.1.1 (2026-08-21)

Fix incorrect risk calculation when the configured temperature sensor does not report in Celsius. The risk formulas are calibrated for Celsius input; Fahrenheit and Kelvin values are now converted automatically based on the sensor's `unit_of_measurement`, with a safe fallback to prior (assume-Celsius) behavior when no unit is set. [#12](https://github.com/Strixx76/mold_risk_index/issues/12)

# 1.1.0 (2023-11-06)

Added translations for de, sk and sv

# 1.0.1 (2023-07-14)

Fix error in HA logs due to unavailability of attached temp / humidity sensors (state: `unkown`) [#4](https://github.com/Strixx76/mold_risk_index/issues/4)

# 1.0.0 (2022-12-29)

Initial release.

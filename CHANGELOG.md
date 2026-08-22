# 1.1.1 (2026-08-21)

Fix incorrect risk calculation when the configured temperature sensor does not report in Celsius. The risk formulas are calibrated for Celsius input; Fahrenheit and Kelvin values are now converted automatically based on the sensor's `unit_of_measurement`, with a safe fallback to prior (assume-Celsius) behavior when no unit is set. [#12](https://github.com/Strixx76/mold_risk_index/issues/12)

# 1.1.0 (2023-11-06)

Added translations for de, sk and sv

# 1.0.1 (2023-07-14)

Fix error in HA logs due to unavailability of attached temp / humidity sensors (state: `unkown`) [#4](https://github.com/Strixx76/mold_risk_index/issues/4)

# 1.0.0 (2022-12-29)

Initial release.

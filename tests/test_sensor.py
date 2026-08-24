"""Regression tests for custom_components/mold_risk_index/sensor.py.

These run against lightweight stubs (see ha_stubs.py), not a real Home
Assistant instance - they catch regressions in this integration's own
logic (formula correctness, listener wiring, dedup/refresh behavior,
warning messages) cheaply and without any HA dependency, but they are not
a substitute for testing against a real Home Assistant instance.
"""

import asyncio
import math

# conftest.py installs the HA stubs before this module is collected.
from homeassistant.core import Event, HomeAssistant, State  # noqa: E402

from custom_components.mold_risk_index import sensor  # noqa: E402


class FakeConfigEntry:
    def __init__(self, title, entry_id, options):
        self.title = title
        self.entry_id = entry_id
        self.options = options
        self.unload_callbacks = []

    def async_on_unload(self, cb):
        self.unload_callbacks.append(cb)


def build(
    temp_state=("20", {"unit_of_measurement": "°C"}),
    hum_state=("85", {}),
    title="Test",
    entry_id="entry1",
):
    """Set up a config entry against fresh stub hass/entry objects and
    return (hass, entry, {entity_name: entity})."""
    hass = HomeAssistant()
    hass._states["sensor.temp"] = State(*temp_state)
    hass._states["sensor.hum"] = State(*hum_state)
    entry = FakeConfigEntry(
        title,
        entry_id,
        {"humidity_entity_id": "sensor.hum", "temperature_entity_id": "sensor.temp"},
    )
    added = []
    asyncio.run(sensor.async_setup_entry(hass, entry, added.extend))
    for entity in added:
        entity.hass = hass
    return hass, entry, {e._attr_name: e for e in added}


def calc_limit_reference(scale, decay, base, floor, temp):
    """Independent reimplementation of the limit formula, for
    cross-checking MoldRiskCalculator.calc_limit without sharing code
    with the thing under test."""
    if 0 <= temp <= 50:
        return max(min(100, round(scale * math.exp(-temp * decay) + base)), floor)
    return 100


LIMIT_PARAMS = {1: (20, 0.15, 73, 72), 2: (17, 0.11, 80, 79), 3: (15, 0.10, 85, 84)}


def fire_state_change(hass, entity_id, new_value, attributes=None):
    """Update a source entity's stubbed state and deliver the resulting
    state_changed event to every listener registered for it."""
    hass._states[entity_id] = State(new_value, attributes or {})
    event = Event(
        "state_changed",
        {"entity_id": entity_id, "new_state": hass._states[entity_id]},
    )
    for listener in list(hass._listeners.get(entity_id, [])):
        listener(event)


def test_initial_values_match_reference_formula():
    _, _, by_name = build(temp_state=("20", {"unit_of_measurement": "°C"}))

    expected_limits = {
        level: calc_limit_reference(*params, 20.0)
        for level, params in LIMIT_PARAMS.items()
    }
    for level, expected in expected_limits.items():
        assert by_name[f"Level {level} Limit"].native_value == expected

    if expected_limits[3] < 85:
        expected_risk = 3
    elif expected_limits[2] < 85:
        expected_risk = 2
    elif expected_limits[1] < 85:
        expected_risk = 1
    else:
        expected_risk = 0
    assert by_name["Current Index"].native_value == expected_risk


def test_unique_id_continuity():
    _, _, by_name = build(entry_id="entry123")

    # Level 1 keeps the unique_id from before per-level entities existed,
    # so upgrading doesn't orphan existing entity_ids/history/automations.
    assert by_name["Level 1 Limit"].unique_id == "entry123-limit"
    assert by_name["Level 2 Limit"].unique_id == "entry123-limit-2"
    assert by_name["Level 3 Limit"].unique_id == "entry123-limit-3"
    assert by_name["Current Index"].unique_id == "entry123-index"


def test_exactly_one_listener_per_source_entity():
    hass, _, _ = build()

    # One shared listener per source entity, not one per entity reading
    # from the calculator (that would be 3 for temp, 2 for humidity).
    assert len(hass._listeners["sensor.temp"]) == 1
    assert len(hass._listeners["sensor.hum"]) == 1


def test_temperature_change_recomputes_and_writes_changed_entities_only():
    hass, _, by_name = build(temp_state=("20", {"unit_of_measurement": "°C"}))
    for entity in by_name.values():
        entity._write_count = 0

    fire_state_change(hass, "sensor.temp", "25", {"unit_of_measurement": "°C"})

    for level, params in LIMIT_PARAMS.items():
        expected = calc_limit_reference(*params, 25.0)
        assert by_name[f"Level {level} Limit"].native_value == expected
        assert by_name[f"Level {level} Limit"]._write_count == 1


def test_same_value_update_writes_nothing():
    hass, _, by_name = build(temp_state=("20", {"unit_of_measurement": "°C"}))
    for entity in by_name.values():
        entity._write_count = 0

    fire_state_change(hass, "sensor.temp", "20", {"unit_of_measurement": "°C"})

    assert all(e._write_count == 0 for e in by_name.values())


def test_humidity_only_change_skips_limit_sensor_refresh_entirely():
    hass, _, by_name = build()
    call_counts = {name: 0 for name in by_name}
    for name, entity in by_name.items():
        original = entity.async_refresh_from_calculator

        # Default args bind each loop iteration's own original/name now,
        # rather than all four wrappers sharing the loop variables' final
        # values (the classic late-binding closure pitfall).
        def wrapper(original=original, name=name):
            call_counts[name] += 1
            return original()

        entity.async_refresh_from_calculator = wrapper

    fire_state_change(hass, "sensor.hum", "90")

    assert call_counts["Level 1 Limit"] == 0
    assert call_counts["Level 2 Limit"] == 0
    assert call_counts["Level 3 Limit"] == 0
    assert call_counts["Current Index"] == 1


def test_bad_temperature_unit_warns_once_at_setup_and_shows_unknown(caplog):
    with caplog.at_level("WARNING"):
        _, _, by_name = build(temp_state=("70", {"unit_of_measurement": "bogus"}))

    unit_warnings = [r for r in caplog.records if "without a supported" in r.message]
    assert len(unit_warnings) == 1

    assert by_name["Level 1 Limit"].native_value is None
    assert by_name["Level 2 Limit"].native_value is None
    assert by_name["Level 3 Limit"].native_value is None
    assert by_name["Current Index"].native_value is None


def test_non_numeric_state_warning_names_the_entity(caplog):
    with caplog.at_level("WARNING"):
        build(temp_state=("garbage", {"unit_of_measurement": "°C"}))

    warnings = [r.message for r in caplog.records if "non-numeric" in r.message]
    assert len(warnings) == 1
    assert "sensor.temp" in warnings[0]


def test_humidity_out_of_range_is_clamped_and_logged(caplog):
    hass, _, by_name = build()
    with caplog.at_level("WARNING"):
        fire_state_change(hass, "sensor.hum", "142")

    warnings = [r.message for r in caplog.records if "outside the valid" in r.message]
    assert len(warnings) == 1
    assert "sensor.hum" in warnings[0]

    # 142% should behave identically to an actual 100% reading (clamped),
    # which at the default 20C fixture is above all three limits (74/82/87).
    assert by_name["Current Index"].native_value == 3


def test_unload_removes_the_listener():
    hass, entry, _ = build()

    assert len(entry.unload_callbacks) == 1
    entry.unload_callbacks[0]()

    assert hass._listeners["sensor.temp"] == []
    assert hass._listeners["sensor.hum"] == []


def test_calc_limit_matches_reference_formula_across_full_domain():
    temp = -20.0
    while temp <= 70.0:
        for level, params in LIMIT_PARAMS.items():
            expected = calc_limit_reference(*params, temp)
            actual = sensor.MoldRiskCalculator.calc_limit(level, temp)
            assert actual == expected, (level, temp, expected, actual)
        temp = round(temp + 0.5, 1)

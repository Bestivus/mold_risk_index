"""Minimal, faithful stubs for the Home Assistant symbols
custom_components/mold_risk_index/sensor.py imports, so the real integration
code can be imported and exercised without installing the full
`homeassistant` package (which is too heavy to be a test dependency for a
single-platform custom component).

Only symbols actually used as runtime values need faithful behavior - most
of sensor.py's HA imports are pure type annotations, which are inert at
runtime under `from __future__ import annotations` and never touch these
stubs at all.
"""

import sys
import types


def install() -> None:
    """Register stub `homeassistant.*` modules in sys.modules."""

    # --- homeassistant.components.sensor ---
    mod_sensor = types.ModuleType("homeassistant.components.sensor")

    class SensorEntity:
        hass = None
        entity_id = None

        def async_write_ha_state(self):
            self._write_count = getattr(self, "_write_count", 0) + 1

    class SensorDeviceClass:
        HUMIDITY = "humidity"
        TEMPERATURE = "temperature"

    class SensorStateClass:
        MEASUREMENT = "measurement"

    mod_sensor.SensorEntity = SensorEntity
    mod_sensor.SensorDeviceClass = SensorDeviceClass
    mod_sensor.SensorStateClass = SensorStateClass

    # --- homeassistant.config_entries ---
    mod_config_entries = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        pass

    mod_config_entries.ConfigEntry = ConfigEntry

    # --- homeassistant.core ---
    mod_core = types.ModuleType("homeassistant.core")

    class Event:
        def __init__(self, event_type, data=None):
            self.event_type = event_type
            self.data = data or {}

    class State:
        def __init__(self, state, attributes=None):
            self.state = state
            self.attributes = attributes or {}

    class HomeAssistant:
        def __init__(self):
            self._states = {}
            self._listeners = {}

        @property
        def states(self):
            hass = self

            class _States:
                def get(self, entity_id):
                    return hass._states.get(entity_id)

            return _States()

    def callback(func):
        return func

    mod_core.Event = Event
    mod_core.State = State
    mod_core.HomeAssistant = HomeAssistant
    mod_core.callback = callback

    # --- homeassistant.const ---
    mod_const = types.ModuleType("homeassistant.const")
    mod_const.ATTR_UNIT_OF_MEASUREMENT = "unit_of_measurement"
    mod_const.PERCENTAGE = "%"
    mod_const.STATE_UNAVAILABLE = "unavailable"
    mod_const.STATE_UNKNOWN = "unknown"

    class UnitOfTemperature:
        CELSIUS = "°C"
        FAHRENHEIT = "°F"
        KELVIN = "K"

    mod_const.UnitOfTemperature = UnitOfTemperature

    class Platform:
        SENSOR = "sensor"

    mod_const.Platform = Platform

    # --- homeassistant.helpers.entity_registry ---
    mod_er = types.ModuleType("homeassistant.helpers.entity_registry")

    def async_get(hass):
        return object()

    def async_validate_entity_id(registry, entity_id):
        return entity_id

    mod_er.async_get = async_get
    mod_er.async_validate_entity_id = async_validate_entity_id

    # --- homeassistant.helpers.entity ---
    mod_entity = types.ModuleType("homeassistant.helpers.entity")

    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    mod_entity.DeviceInfo = DeviceInfo

    # --- homeassistant.helpers.entity_platform ---
    mod_entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    mod_entity_platform.AddEntitiesCallback = object

    # --- homeassistant.helpers.event ---
    mod_event = types.ModuleType("homeassistant.helpers.event")

    def async_track_state_change_event(hass, entity_ids, action):
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        for eid in entity_ids:
            hass._listeners.setdefault(eid, []).append(action)

        def _unsub():
            for eid in entity_ids:
                if action in hass._listeners.get(eid, []):
                    hass._listeners[eid].remove(action)

        return _unsub

    mod_event.async_track_state_change_event = async_track_state_change_event

    # --- homeassistant.util.unit_conversion ---
    mod_unit_conversion = types.ModuleType("homeassistant.util.unit_conversion")

    class TemperatureConverter:
        VALID_UNITS = {"°C", "°F", "K"}

        @staticmethod
        def convert(value, from_unit, to_unit):
            # Real conversion math, faithful to HA's actual formulas.
            if from_unit == "°F":
                celsius = (value - 32) * 5 / 9
            elif from_unit == "K":
                celsius = value - 273.15
            else:
                celsius = value
            if to_unit == "°C":
                return celsius
            raise NotImplementedError("stub only converts to Celsius")

    mod_unit_conversion.TemperatureConverter = TemperatureConverter

    # --- helpers package placeholders ---
    mod_helpers = types.ModuleType("homeassistant.helpers")
    mod_util = types.ModuleType("homeassistant.util")
    mod_ha = types.ModuleType("homeassistant")
    mod_ha_components = types.ModuleType("homeassistant.components")

    modules = {
        "homeassistant": mod_ha,
        "homeassistant.components": mod_ha_components,
        "homeassistant.components.sensor": mod_sensor,
        "homeassistant.config_entries": mod_config_entries,
        "homeassistant.core": mod_core,
        "homeassistant.const": mod_const,
        "homeassistant.helpers": mod_helpers,
        "homeassistant.helpers.entity_registry": mod_er,
        "homeassistant.helpers.entity": mod_entity,
        "homeassistant.helpers.entity_platform": mod_entity_platform,
        "homeassistant.helpers.event": mod_event,
        "homeassistant.util": mod_util,
        "homeassistant.util.unit_conversion": mod_unit_conversion,
    }
    sys.modules.update(modules)

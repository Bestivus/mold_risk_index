""" Risk of mold growth at present temperature and humidity. """
from __future__ import annotations

from math import exp
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_HUM_ID,
    CONF_TEMP_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """ Initialize mold risk index config entry. """
    registry = er.async_get(hass)
    
    hum_entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_HUM_ID]
    )
    temp_entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_TEMP_ID]
    )
    mold_calc = MoldRiskCalculator(hum_entity_id, temp_entity_id)
    # Prime the calculator with current source states before any entity
    # exists, so entities can read an already-computed value at construction
    # instead of each faking its own priming event.
    mold_calc.async_update_from_state(temp_entity_id, hass.states.get(temp_entity_id))
    mold_calc.async_update_from_state(hum_entity_id, hass.states.get(hum_entity_id))

    limit_entities = [
        MoldRiskLimitSensor(
            config_entry.title,
            config_entry.entry_id,
            mold_calc,
            level,
        )
        for level in (1, 2, 3)
    ]
    index_entity = MoldRiskIndexSensor(
        config_entry.title,
        config_entry.entry_id,
        mold_calc,
    )
    entities: list[MoldRiskBaseSensor] = [*limit_entities, index_entity]
    async_add_entities(entities)

    @callback
    def _async_source_changed(event: Event) -> None:
        """ Update the shared calculator once, then refresh affected entities. """
        entity_id = event.data["entity_id"]
        mold_calc.async_update_from_state(entity_id, event.data["new_state"])
        # Level N Limit is a pure function of temperature alone (humidity
        # never appears in calc_limit_1/2/3), so a humidity-only change
        # cannot affect it - only Current Index depends on both.
        refresh_targets = entities if entity_id == temp_entity_id else (index_entity,)
        for entity in refresh_targets:
            entity.async_refresh_from_calculator()

    # Registered once per config entry (not once per entity), so a single
    # source state change is processed exactly once regardless of how many
    # entities read from the calculator. Tied to the config entry's own
    # unload rather than any one entity's, since no single entity owns it.
    config_entry.async_on_unload(
        async_track_state_change_event(
            hass, [temp_entity_id, hum_entity_id], _async_source_changed
        )
    )


class MoldRiskCalculator:
    """ Calculate the limits and risk of mold growth. """
    def __init__(self, hum_entity_id: str, temp_entity_id: str):
        """ Initialize the calculator. """
        self._hum_entity_id = hum_entity_id
        self._temp_entity_id = temp_entity_id

        self.humidity: float | None = None
        self.temperature: float | None = None
        self.risk: int | None = None
        self.humidity_limit_level_1: int | None = None
        self.humidity_limit_level_2: int | None = None
        self.humidity_limit_level_3: int | None = None
    
    def calc_limit_1(self, temp: float | int) -> int:
        """ Calculate limit for risk level 1 """
        if 0 <= temp <= 50:
            limit = round(20 * exp( -temp * 0.15 ) + 73)
            return max(min(100,limit),72)
        else:
            return 100
    
    def calc_limit_2(self, temp: float | int) -> int:
        """ Calculate limit for risk level 2 """
        if 0 <= temp <= 50:
            limit = round(17 * exp( -temp * 0.11 ) + 80)
            return max(min(100,limit),79)
        else:
            return 100
        
    def calc_limit_3(self, temp: float | int) -> int:
        """ Calculate limit for risk level 3 """
        if 0 <= temp <= 50:
            limit = round(15 * exp( -temp * 0.10 ) + 85)
            return max(min(100,limit),84)
        else:
            return 100

    @staticmethod
    def _coerce_temperature_to_celsius(
        value: float, unit: str | None, entity_id: str
    ) -> float | None:
        """Convert a raw temperature reading to Celsius.

        The risk formulas in calc_limit_1/2/3 are calibrated for Celsius
        input, so everything downstream of this function assumes Celsius.
        This is the only place in the integration that should read a
        temperature entity's unit_of_measurement -- if another input path
        for temperature is ever added, route it through here too.

        Returns None (after logging a warning) if the unit is missing or
        not one Home Assistant recognizes as a temperature unit, rather
        than guessing and risking a silently wrong calculation.
        """
        if unit not in TemperatureConverter.VALID_UNITS:
            _LOGGER.warning(
                "Temperature sensor %s reported without a supported "
                "unit (got %s); expected one of %s. Ignoring this "
                "reading",
                entity_id,
                unit,
                sorted(TemperatureConverter.VALID_UNITS),
            )
            return None
        return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)

    @callback
    def async_update_from_state(self, entity_id: str, state: State | None) -> None:
        """ Update calculator state from a source entity's current state. """
        if (
            state is None
            or state.state is None
            or state.state
            in [
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ]
        ):
            new_state = None
        else:
            try:
                new_state = float(state.state)
            except ValueError:
                _LOGGER.warning(
                    "Sensor %s reported a non-numeric state (%s); "
                    "only numerical states are supported for input sensors",
                    entity_id,
                    state.state,
                )
                new_state = None

        if entity_id == self._temp_entity_id:
            if new_state is not None:
                unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                new_state = self._coerce_temperature_to_celsius(
                    new_state, unit, self._temp_entity_id
                )
            if new_state == self.temperature:
                return
            self.temperature = new_state
            self._calc_limit()
            self._calc_risk()

        if entity_id == self._hum_entity_id:
            if new_state is not None and new_state > 100:
                new_state = 100
            if new_state is not None and new_state < 0:
                new_state = 0
            if new_state == self.humidity:
                return
            self.humidity = new_state
            self._calc_risk()

    @callback
    def _calc_limit(self) -> None:
        """ Calculate limits. """
        # Without temperature no calculations can be done
        if self.temperature is None:
            self.humidity_limit_level_1 = None
            self.humidity_limit_level_2 = None
            self.humidity_limit_level_3 = None
            return

        self.humidity_limit_level_1 = self.calc_limit_1(self.temperature)
        self.humidity_limit_level_2 = self.calc_limit_2(self.temperature)
        self.humidity_limit_level_3 = self.calc_limit_3(self.temperature)

    def limit_for_level(self, level: int) -> int | None:
        """ Return the calculated humidity limit for a risk level (1-3). """
        return {
            1: self.humidity_limit_level_1,
            2: self.humidity_limit_level_2,
            3: self.humidity_limit_level_3,
        }[level]

    @callback
    def _calc_risk(self) -> None:
        """ Calculate risk. """
        # Without temperature or humidity no calculations can be done
        if self.humidity is None or self.temperature is None:
            self.risk = None
            return

        if self.humidity > self.humidity_limit_level_3:
            # Mold will start grow in less than 4 weeks
            self.risk = 3
        elif self.humidity > self.humidity_limit_level_2:
            # Mold will start grow in 4 to 8 weeks
            self.risk = 2
        elif self.humidity > self.humidity_limit_level_1:
            # Mold will start after 8 weeks or more
            self.risk = 1
        else:
            self.risk = 0


class MoldRiskBaseSensor(SensorEntity):
    """ Base class for mold risk index sensors. """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        name: str,
        entry_id: str,
        mold_calc: MoldRiskCalculator
    ) -> None:
        """ Initialize the base sensor. """
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=name,
            )
        self._entry_id = entry_id
        self._mold_calc = mold_calc


class MoldRiskLimitSensor(MoldRiskBaseSensor):
    """ Representation of the humidity limit sensor for one risk level. """
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_icon = "mdi:water-percent-alert"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        name: str,
        entry_id: str,
        mold_calc: MoldRiskCalculator,
        level: int,
    ) -> None:
        """ Initialize the limit sensor for one risk level. """
        super().__init__(name, entry_id, mold_calc)
        self._level = level
        self._attr_name = f"Level {level} Limit"
        self._limit = mold_calc.limit_for_level(level)

    @callback
    def async_refresh_from_calculator(self) -> None:
        """ Sync from the calculator's current value; write state if changed. """
        limit = self._mold_calc.limit_for_level(self._level)
        if limit != self._limit:
            self._limit = limit
            self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        """ Return the state of the sensor. """
        return self._limit

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        if self._level == 1:
            # Preserve the unique_id from before per-level entities existed,
            # so existing entity_ids and automations keep working.
            return f"{self._entry_id}-limit"
        return f"{self._entry_id}-limit-{self._level}"


class MoldRiskIndexSensor(MoldRiskBaseSensor):
    """ Representation of a mold risk index sensor. """
    _attr_icon = "mdi:alert-outline"
    _attr_name = "Current Index"

    def __init__(
        self,
        name: str,
        entry_id: str,
        mold_calc: MoldRiskCalculator,
    ) -> None:
        """ Initialize the index sensor. """
        super().__init__(name, entry_id, mold_calc)
        self._risk = mold_calc.risk

    @callback
    def async_refresh_from_calculator(self) -> None:
        """ Sync from the calculator's current value; write state if changed. """
        if self._mold_calc.risk != self._risk:
            self._risk = self._mold_calc.risk
            self.async_write_ha_state()
    
    @property
    def native_value(self) -> int | None:
        """ Return the state of the sensor. """
        return self._risk

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self._entry_id}-index"

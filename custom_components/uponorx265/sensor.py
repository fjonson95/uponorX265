import logging
from datetime import datetime

import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SIGNAL_UPONOR_STATE_UPDATE, DEVICE_MANUFACTURER, STATUS_OK

_LOGGER = logging.getLogger(__name__)

from .helper import get_unique_id_from_config_entry

async def async_setup_entry(hass, entry, async_add_entities):
    unique_id = get_unique_id_from_config_entry(entry)
    state_proxy = hass.data[unique_id]["state_proxy"]

    entities = []

    # Gateway diagnostic sensor (one per integration)
    entities.append(UponorGatewayStatusSensor(unique_id, state_proxy))

    seen_controllers = set()
    for thermostat in hass.data[unique_id]["thermostats"]:
        controller = thermostat.split('_')[0]
        if controller not in seen_controllers:
            seen_controllers.add(controller)
            entities.append(UponorRoomAvg(unique_id, state_proxy, thermostat))
            # Controller diagnostic sensor (one per controller)
            entities.append(UponorControllerStatusSensor(unique_id, state_proxy, controller))

    for thermostat in hass.data[unique_id]["thermostats"]:
        room_name = state_proxy.get_room_name(thermostat)
        _LOGGER.debug(f"Adding sensors for {room_name} (thermostat ID: {thermostat})")
        entities.append(UponorRoomCurrentTemperatureSensor(unique_id, state_proxy, thermostat))
        # Thermostat diagnostic status sensor
        entities.append(UponorThermostatStatusSensor(unique_id, state_proxy, thermostat))

        if state_proxy.has_floor_temperature(thermostat):
            entities.append(UponorFloorTemperatureSensor(unique_id, state_proxy, thermostat))
            _LOGGER.debug(f"Added floor sensor for: {room_name}")

        if state_proxy.has_humidity_sensor(thermostat):
            entities.append(UponorHumiditySensor(unique_id, state_proxy, thermostat))
            _LOGGER.debug(f"Added humidity sensor for: {room_name}")

    _LOGGER.debug(f"Total number of sensors added: {len(entities)}")
    async_add_entities(entities, update_before_add=False)


# ---------------------------------------------------------------------------
# Diagnostic sensors
# ---------------------------------------------------------------------------

class UponorThermostatStatusSensor(SensorEntity):
    """Diagnostic sensor showing alarm/error status for a single thermostat."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, unique_instance_id, state_proxy, thermostat):
        self._unique_instance_id = unique_instance_id
        self._state_proxy = state_proxy
        self._thermostat = thermostat
        self._controller = thermostat.split('_')[0]
        self._room_name = state_proxy.get_room_name(thermostat)
        self._attr_name = f"{self._room_name} Status"
        self._attr_unique_id = f"{unique_instance_id}_{state_proxy.get_thermostat_id(thermostat)}_status"

    @property
    def device_info(self):
        return {
            "identifiers": {(self._unique_instance_id, self._state_proxy.get_thermostat_id(self._thermostat))},
            "name": self._room_name,
            "manufacturer": DEVICE_MANUFACTURER,
            "model": self._state_proxy.get_thermostat_model(self._thermostat),
            "sw_version": self._state_proxy.get_version(self._thermostat),
            "serial_number": self._state_proxy.get_thermostat_id(self._thermostat),
            "via_device": (self._unique_instance_id, self._state_proxy.get_controller_id(self._controller)),
        }

    @property
    def available(self):
        return self._state_proxy.is_available()

    @property
    def should_poll(self):
        return False

    @property
    def native_value(self):
        return self._state_proxy.get_status(self._thermostat)

    @property
    def icon(self):
        status = self._state_proxy.get_status(self._thermostat)
        return "mdi:check-circle-outline" if status == STATUS_OK else "mdi:alert-circle"

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPONOR_STATE_UPDATE, self._update_callback)
        )

    @callback
    def _update_callback(self):
        self.async_schedule_update_ha_state(True)


class UponorControllerStatusSensor(SensorEntity):
    """Diagnostic sensor showing communication status for a controller."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, unique_instance_id, state_proxy, controller):
        self._unique_instance_id = unique_instance_id
        self._state_proxy = state_proxy
        self._controller = controller
        self._controller_name = state_proxy.get_controller_name(controller)
        self._attr_name = f"{self._controller_name} Status"
        self._attr_unique_id = f"{unique_instance_id}_{state_proxy.get_controller_id(controller)}_status"

    @property
    def device_info(self):
        return {
            "identifiers": {(self._unique_instance_id, self._state_proxy.get_controller_id(self._controller))},
            "name": self._controller_name,
            "model": self._state_proxy.get_controller_hardware(self._controller),
            "manufacturer": DEVICE_MANUFACTURER,
            "sw_version": self._state_proxy.get_controller_version(self._controller),
            "serial_number": self._state_proxy.get_controller_id(self._controller),
            "via_device": (self._unique_instance_id, self._state_proxy.get_gateway_id()),
        }

    @property
    def available(self):
        return self._state_proxy.is_available()

    @property
    def should_poll(self):
        return False

    @property
    def native_value(self):
        return self._state_proxy.get_controller_status(self._controller)

    @property
    def icon(self):
        return "mdi:check-circle-outline" if self._state_proxy.is_available() else "mdi:alert-circle"

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPONOR_STATE_UPDATE, self._update_callback)
        )

    @callback
    def _update_callback(self):
        self.async_schedule_update_ha_state(True)


class UponorGatewayStatusSensor(SensorEntity):
    """Diagnostic sensor showing online/offline status for the Uponor gateway."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, unique_instance_id, state_proxy):
        self._unique_instance_id = unique_instance_id
        self._state_proxy = state_proxy
        self._attr_name = "Uponor Gateway Status"
        self._attr_unique_id = f"{unique_instance_id}_gateway_status"

    @property
    def device_info(self):
        return {
            "identifiers": {(self._unique_instance_id, self._state_proxy.get_gateway_id())},
            "name": "Uponor Gateway",
            "manufacturer": DEVICE_MANUFACTURER,
            "model": self._state_proxy.get_model(),
        }

    @property
    def available(self):
        # Always available so the sensor can show "Offline" rather than going unavailable
        return True

    @property
    def should_poll(self):
        return False

    @property
    def native_value(self):
        return self._state_proxy.get_gateway_status()

    @property
    def icon(self):
        return "mdi:lan-connect" if self._state_proxy.is_available() else "mdi:lan-disconnect"

    @property
    def extra_state_attributes(self):
        last = self._state_proxy.get_last_update()
        return {
            "last_successful_update": last.isoformat() if last else None,
        }

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPONOR_STATE_UPDATE, self._update_callback)
        )

    @callback
    def _update_callback(self):
        self.async_schedule_update_ha_state(True)


# ---------------------------------------------------------------------------
# Regular measurement sensors
# ---------------------------------------------------------------------------

class UponorFloorTemperatureSensor(SensorEntity):
    def __init__(self, unique_instance_id, state_proxy, thermostat):
        self._unique_instance_id = unique_instance_id
        self._state_proxy = state_proxy
        self._thermostat = thermostat
        self._name = state_proxy.get_room_name(self._thermostat)         
        self._controller = thermostat.split('_')[0]
        self._attr_name = f"{self._name} Floor Temperature"
        self._attr_unique_id = f"{unique_instance_id}_{state_proxy.get_thermostat_id(thermostat)}_floor_temp"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self):
        return {
            "identifiers": {(self._unique_instance_id, self._state_proxy.get_thermostat_id(self._thermostat))},
            "name": self._name,
            "manufacturer": DEVICE_MANUFACTURER,
            "model": self._state_proxy.get_model(),
            "sw_version": self._state_proxy.get_version(self._thermostat),
            "serial_number": self._state_proxy.get_thermostat_id(self._thermostat),
            "via_device": (self._unique_instance_id, self._state_proxy.get_controller_id(self._controller)),
        }

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self._state_proxy.is_available() and self._state_proxy.has_floor_temperature(self._thermostat)

    @property
    def native_value(self):
        return self._state_proxy.get_floor_temperature(self._thermostat)

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPONOR_STATE_UPDATE, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        """Update sensor state. when data updates"""
        _LOGGER.debug(f"Updating state for {self._attr_name} with ID {self._attr_unique_id}")
        self.async_schedule_update_ha_state(True)     

class UponorRoomCurrentTemperatureSensor(SensorEntity):

    def __init__(self, unique_instance_id, state_proxy, thermostat):
        self._unique_instance_id = unique_instance_id
        self._state_proxy = state_proxy
        self._thermostat = thermostat
        self._controller = thermostat.split('_')[0]
        self._name = state_proxy.get_room_name(thermostat)
        self._attr_name = f"{self._name} Current Temperature"
        self._attr_unique_id = f"{unique_instance_id}_{state_proxy.get_thermostat_id(thermostat)}_current_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self):
        return {
            "identifiers": {(self._unique_instance_id, self._state_proxy.get_thermostat_id(self._thermostat))},
            "name": self._name,
            "manufacturer": DEVICE_MANUFACTURER,
            "model": self._state_proxy.get_thermostat_model(self._thermostat),
            "sw_version": self._state_proxy.get_version(self._thermostat),
            "serial_number": self._state_proxy.get_thermostat_id(self._thermostat),
            "via_device": (self._unique_instance_id, self._state_proxy.get_controller_id(self._controller)),
        }

    @property
    def available(self):
        return self._state_proxy.is_available()

    @property
    def native_value(self):
        return self._state_proxy.get_temperature(self._thermostat)

    @property
    def should_poll(self):
        return False

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPONOR_STATE_UPDATE, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        """Update sensor state. when data updates"""
        _LOGGER.debug(f"Updating state for {self._attr_name} with ID {self._attr_unique_id}")
        self.async_schedule_update_ha_state(True)


class UponorHumiditySensor(SensorEntity):
    def __init__(self, unique_instance_id, state_proxy, thermostat):
        self._unique_instance_id = unique_instance_id
        self._state_proxy = state_proxy
        self._thermostat = thermostat
        self._controller = thermostat.split('_')[0]
        self._name = state_proxy.get_room_name(thermostat)
        self._attr_name = f"{self._name} humidity"
        self._attr_unique_id = f"{unique_instance_id}_{state_proxy.get_thermostat_id(thermostat)}_rh"
        self._attr_device_class = SensorDeviceClass.HUMIDITY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self):
        return {
            "identifiers": {(self._unique_instance_id, self._state_proxy.get_thermostat_id(self._thermostat))},
            "name": self._name,
            "manufacturer": DEVICE_MANUFACTURER,
            "model": self._state_proxy.get_thermostat_model(self._thermostat), 
            "sw_version": self._state_proxy.get_version(self._thermostat),
            "serial_number": self._state_proxy.get_thermostat_id(self._thermostat),
            "via_device": (self._unique_instance_id, self._state_proxy.get_controller_id(self._controller)),
        }

    @property
    def available(self):
        """Return True if the sensor is available."""
        return self._state_proxy.is_available() and self._state_proxy.has_humidity_sensor(self._thermostat)

    @property
    def native_value(self):
        return self._state_proxy.get_humidity(self._thermostat)

    @property
    def should_poll(self):
        return False

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPONOR_STATE_UPDATE, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        _LOGGER.debug(f"Updating state for {self._attr_name} with ID {self._attr_unique_id}")
        self.async_schedule_update_ha_state(True)


class UponorRoomAvg(SensorEntity):
    def __init__(self, unique_instance_id, state_proxy, thermostat):
        self._unique_instance_id = unique_instance_id
        self._state_proxy = state_proxy
        self._controller = thermostat.split('_')[0]
        self._name = state_proxy.get_controller_name(self._controller)
        self._attr_name = f"{self._name} Room avg temp"
        self._attr_unique_id = f"{unique_instance_id}_{state_proxy.get_controller_id(self._controller)}_average_room_temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self):
        return {
            "identifiers": {(self._unique_instance_id, self._state_proxy.get_controller_id(self._controller))},
            "name": self._name,
            "model": self._state_proxy.get_controller_hardware(self._controller),
            "manufacturer": DEVICE_MANUFACTURER,
            "sw_version": self._state_proxy.get_controller_version(self._controller),
            "serial_number": self._state_proxy.get_controller_id(self._controller),
            "via_device": (self._unique_instance_id, self._state_proxy.get_gateway_id()),
        }

    @property
    def available(self):
        return self._state_proxy.is_available()

    @property
    def should_poll(self):
        return False

    @property
    def native_value(self):
        return self._state_proxy.get_controller_avgtemp(self._controller)

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPONOR_STATE_UPDATE, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        """Update sensor state. when data updates"""
        _LOGGER.debug(f"Updating state for {self._attr_name} with ID {self._attr_unique_id}")
        self.async_schedule_update_ha_state(True)
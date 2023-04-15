"""Implementation of Garo Wallbox sensors."""
import logging

import voluptuous as vol

from homeassistant.const import (
    UnitOfTemperature,
    UnitOfEnergy,
    UnitOfElectricCurrent,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorEntity,
)

from homeassistant.helpers import config_validation as cv, entity_platform

from . import DOMAIN as GARO_DOMAIN

from .garo import GaroDevice, Mode, Status
from .const import ATTR_MODES, SERVICE_SET_MODE, SERVICE_SET_CURRENT_LIMIT

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config,  # pylint: disable=unused-argument
    async_add_entities,  # pylint: disable=unused-argument
    discovery_info=None,  # pylint: disable=unused-argument
):
    """Setup platform."""


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up using config_entry."""
    device = hass.data[GARO_DOMAIN].get(entry.entry_id)
    async_add_entities(
        [
            GaroMainSensor(device),
            GaroSensor(
                device,
                "Status",
                "status",
            ),
            GaroSensor(
                device,
                "Charging Current",
                "current_charging_current",
                UnitOfElectricCurrent.AMPERE,
            ),
            GaroSensor(
                device,
                "Charging Power",
                "current_charging_power",
                UnitOfPower.WATT,
            ),
            GaroSensor(
                device,
                "Phases",
                "nr_of_phases",
            ),
            GaroSensor(
                device,
                "Current Limit",
                "current_limit",
                UnitOfElectricCurrent.AMPERE,
            ),
            GaroSensor(
                device,
                "Pilot Level",
                "pilot_level",
                UnitOfElectricCurrent.AMPERE,
            ),
            GaroSensor(
                device,
                "Session Energy",
                "acc_session_energy",
                UnitOfEnergy.WATT_HOUR,
            ),
            GaroSensor(
                device,
                "Total Energy",
                "latest_reading",
                UnitOfEnergy.WATT_HOUR,
            ),
            GaroSensor(
                device,
                "Total Energy (kWh)",
                "latest_reading_k",
                UnitOfEnergy.KILO_WATT_HOUR,
            ),
            GaroSensor(
                device,
                "Temperature",
                "current_temperature",
                UnitOfTemperature.CELSIUS,
            ),
        ]
    )

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_MODE,
        {
            vol.Required("mode"): cv.string,
        },
        "async_set_mode",
    )
    platform.async_register_entity_service(
        SERVICE_SET_CURRENT_LIMIT,
        {
            vol.Required("limit"): cv.positive_int,
        },
        "async_set_current_limit",
    )


class GaroMainSensor(Entity):
    """Class representing Garo Wallbox main sensor."""

    def __init__(self, device: GaroDevice) -> None:
        """Initialize the sensor."""
        self._device = device
        self._name = f"{device.name}"
        self._sensor = "sensor"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device.id_}-{self._sensor}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        return "mdi:car-electric"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.status.mode.name

    @property
    def modes(self):
        """Return the current GARO Wallbox mode."""
        return [f.name for f in Mode]

    async def async_set_mode(self, mode):
        """Set the GARO Wallbox mode."""
        await self._device.set_mode(Mode[mode])

    async def async_set_current_limit(self, limit):
        """Set the GARO Wallbox charging current limit."""
        await self._device.set_current_limit(limit)

    async def async_update(self):
        """Update Garo Wallbox status."""
        await self._device.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._device.device_info

    @property
    def device_state_attributes(self):
        attrs = {}
        try:
            attrs[ATTR_MODES] = self.modes
        except KeyError:
            pass
        return attrs


class GaroSensor(SensorEntity):
    """Class representing Garo Wallbox sensor."""

    def __init__(self, device: GaroDevice, name, sensor, unit=None) -> None:
        """Initialize the sensor."""
        self._device = device
        self._name = f"{device.name} {name}"
        self._sensor = sensor
        self._attr_native_unit_of_measurement = unit
        if self._sensor in ("latest_reading", "latest_reading_k"):
            _LOGGER.info("Initiating State sensors %s", self._name)
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_device_class = SensorDeviceClass.ENERGY

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device.id_}-{self._sensor}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        icon = None
        if self._sensor == "current_temperature":
            icon = "mdi:thermometer"
        elif self._sensor == "current_charging_current":
            icon = "mdi:flash"
        elif self._sensor == "current_charging_power":
            icon = "mdi:flash"
        elif self._sensor == "current_limit":
            icon = "mdi:flash"
        elif self._sensor == "pilot_level":
            icon = "mdi:flash"
        elif self._sensor == "acc_session_energy":
            icon = "mdi:flash"
        elif self._sensor == "latest_reading":
            icon = "mdi:flash"
        elif self._sensor == "latest_reading_k":
            icon = "mdi:flash"
        elif self._sensor == "status":
            switcher = {
                Status.CABLE_FAULT: "mdi:alert",
                Status.CHANGING: "mdi:update",
                Status.CHARGING: "mdi:battery-charging",
                Status.CHARGING_CANCELLED: "mdi:cancel",
                Status.CHARGING_FINISHED: "mdi:battery",
                Status.CHARGING_PAUSED: "mdi:pause",
                Status.CONNECTED: "mdi:power-plug",
                Status.CONTACTOR_FAULT: "mdi:alert",
                Status.DISABLED: "mdi:stop-circle-outline",
                Status.CRITICAL_TEMPERATURE: "mdi:alert",
                Status.DC_ERROR: "mdi:alert",
                Status.INITIALIZATION: "mdi:timer-sand",
                Status.LOCK_FAULT: "mdi:alert",
                Status.NOT_CONNECTED: "mdi:power-plug-off",
                Status.OVERHEAT: "mdi:alert",
                Status.RCD_FAULT: "mdi:alert",
                Status.SEARCH_COMM: "mdi:help",
                Status.VENT_FAULT: "mdi:alert",
                Status.UNAVAILABLE: "mdi:alert",
            }
            icon = switcher.get(self._device.status.status, None)
        elif self._sensor == "nr_of_phases":
            if self.state == 1:
                icon = "mdi:record-circle-outline"
            else:
                icon = "mdi:google-circles-communities"
        return icon

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._sensor == "status":
            return self.status_as_str()

        return self._device.status.__dict__[self._sensor]

    async def async_update(self):
        """Update the Garo Wallbox status."""
        await self._device.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._device.device_info

    def status_as_str(self):
        """Return status as a string."""
        switcher = {
            Status.CABLE_FAULT: "Cable fault",
            Status.CHANGING: "Changing...",
            Status.CHARGING: "Charging",
            Status.CHARGING_CANCELLED: "Charging cancelled",
            Status.CHARGING_FINISHED: "Charging finished",
            Status.CHARGING_PAUSED: "Charging paused",
            Status.DISABLED: "Charging disabled",
            Status.CONNECTED: "Vehicle connected",
            Status.CONTACTOR_FAULT: "Contactor fault",
            Status.CRITICAL_TEMPERATURE: "Overtemperature, charging cancelled",
            Status.DC_ERROR: "DC error",
            Status.INITIALIZATION: "Charger starting...",
            Status.LOCK_FAULT: "Lock fault",
            Status.NOT_CONNECTED: "Vehicle not connected",
            Status.OVERHEAT: "Overtemperature, charging temporarily restricted to 6A",
            Status.RCD_FAULT: "RCD fault",
            Status.SEARCH_COMM: "Vehicle connected",
            Status.VENT_FAULT: "Ventilation required",
            Status.UNAVAILABLE: "Unavailable",
        }
        return switcher.get(self._device.status.status, "Unknown")

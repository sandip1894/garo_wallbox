"""Implementation of Garo Wallbox sensors."""
import logging
from typing import Any

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
from .const import SERVICE_SET_MODE, SERVICE_SET_CURRENT_LIMIT

_LOGGER = logging.getLogger(__name__)


# TODO is it needed? What happens if removed?
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
                device_class=SensorDeviceClass.ENUM,
                icon_fn=_status_icon,
            ),
            GaroSensor(
                device,
                "Charging Current",
                "current_charging_current",
                unit=UnitOfElectricCurrent.AMPERE,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.CURRENT,
                icon="mdi:flash",
            ),
            GaroSensor(
                device,
                "Charging Power",
                "current_charging_power",
                unit=UnitOfPower.WATT,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.POWER,
                icon="mdi:flash",
            ),
            GaroSensor(
                device,
                "Phases",
                "nr_of_phases",
                icon_fn=_nr_of_phases_icon,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            GaroSensor(
                device,
                "Current Limit",
                "current_limit",
                unit=UnitOfElectricCurrent.AMPERE,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.CURRENT,
                icon="mdi:flash",
            ),
            GaroSensor(
                device,
                "Pilot Level",
                "pilot_level",
                unit=UnitOfElectricCurrent.AMPERE,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.CURRENT,
                icon="mdi:flash",
            ),
            GaroSensor(
                device,
                "Session Energy",
                "acc_session_energy",
                unit=UnitOfEnergy.WATT_HOUR,
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                icon="mdi:flash",
            ),
            GaroSensor(
                device,
                "Total Energy",
                "latest_reading",
                unit=UnitOfEnergy.WATT_HOUR,
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                icon="mdi:flash",
            ),
            GaroSensor(
                device,
                "Total Energy (kWh)",
                "latest_reading_k",
                unit=UnitOfEnergy.KILO_WATT_HOUR,
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                icon="mdi:flash",
            ),
            GaroSensor(
                device,
                "Temperature",
                "current_temperature",
                unit=UnitOfTemperature.CELSIUS,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.TEMPERATURE,
                icon="mdi:thermometer",
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
        self._attr_name = f"{device.name}"
        self._attr_unique_id = f"{self._device.id_}-sensor"
        self._attr_icon = "mdi:car-electric"
        self._attr_device_info = device.device_info

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.status.mode.name

    async def async_set_mode(self, mode):
        """Set the GARO Wallbox mode."""
        await self._device.set_mode(Mode[mode])

    async def async_set_current_limit(self, limit):
        """Set the GARO Wallbox charging current limit."""
        await self._device.set_current_limit(limit)

    async def async_update(self):
        """Update Garo Wallbox status."""
        await self._device.async_update()


class GaroSensor(SensorEntity):
    """Class representing Garo Wallbox sensor."""

    def __init__(
        self,
        device: GaroDevice,
        name,
        sensor,
        unit=None,
        state_class=None,
        device_class=None,
        icon=None,
        icon_fn=None,
    ) -> None:
        """Initialize the sensor."""

        self._device = device
        self._sensor = sensor

        self._attr_name = f"{device.name} {name}"
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{device.id_}-{sensor}"
        self._attr_device_info = device.device_info

        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_icon_fn = icon_fn

    @property
    def icon(self):
        """Return the icon of the sensor."""
        if self._attr_icon_fn is None:
            return super().icon

        return self._attr_icon_fn(self.native_value)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._device.status.__dict__[self._sensor]

    async def async_update(self):
        """Update the Garo Wallbox status."""
        await self._device.async_update()


def _status_icon(value):
    return {
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
    }.get(value, None)


def _nr_of_phases_icon(value):
    if value == 1:
        return "mdi:record-circle-outline"
    return "mdi:google-circles-communities"

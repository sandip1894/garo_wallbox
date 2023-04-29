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

    # Add chargebox entities
    async_add_entities(
        [
            GaroMainSensor(device),
            GaroSensor(
                device,
                "Temperature",
                "temperature",
                unit=UnitOfTemperature.CELSIUS,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.TEMPERATURE,
                extra_attributes=["temperature_warning", "temperature_cutoff"],
                icon="mdi:thermometer",
            ),
            GaroSensor(
                device,
                "Current Limit",
                "current_limit",
                unit=UnitOfElectricCurrent.AMPERE,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.CURRENT,
                extra_attributes=["factory_current_limit", "switch_current_limit"],
                icon="mdi:flash",
            ),
        ]
    )

    # Add charger entities
    for charger in device.chargers:
        async_add_entities(
            [
                GaroSensor(
                    device,
                    "Status",
                    "status",
                    group=charger,
                    device_class=SensorDeviceClass.ENUM,
                    extra_attributes=["status_descr", "nr_of_phases"],
                    icon_fn=_status_icon,
                ),
                GaroSensor(
                    device,
                    "Charging Current",
                    "charging_current",
                    group=charger,
                    unit=UnitOfElectricCurrent.AMPERE,
                    state_class=SensorStateClass.MEASUREMENT,
                    device_class=SensorDeviceClass.CURRENT,
                    extra_attributes=["pilot_level", "min_current_limit"],
                    icon="mdi:flash",
                ),
                GaroSensor(
                    device,
                    "Charging Power",
                    "charging_power",
                    group=charger,
                    unit=UnitOfPower.WATT,
                    state_class=SensorStateClass.MEASUREMENT,
                    device_class=SensorDeviceClass.POWER,
                    icon="mdi:flash",
                ),
                GaroSensor(
                    device,
                    "Session Energy",
                    "session_acc_energy",
                    group=charger,
                    unit=UnitOfEnergy.WATT_HOUR,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    device_class=SensorDeviceClass.ENERGY,
                    extra_attributes=[
                        "session_start_energy",
                        "session_start_time",
                        "session_duration",
                    ],
                    icon="mdi:flash",
                ),
                GaroSensor(
                    device,
                    "Total Energy",
                    "acc_energy",
                    group=charger,
                    unit=UnitOfEnergy.WATT_HOUR,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    device_class=SensorDeviceClass.ENERGY,
                    icon="mdi:flash",
                ),
                GaroSensor(
                    device,
                    "Total Energy (kWh)",
                    "acc_energy_k",
                    group=charger,
                    unit=UnitOfEnergy.KILO_WATT_HOUR,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    device_class=SensorDeviceClass.ENERGY,
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
        group=None,
        unit=None,
        state_class=None,
        device_class=None,
        icon=None,
        icon_fn=None,
        extra_attributes=None,
    ) -> None:
        """Initialize the sensor."""

        self._device = device
        self._groupid = group and group[1]
        self._sensor = sensor
        self._extra_attributes = extra_attributes

        self._attr_native_unit_of_measurement = unit

        if group is None:
            self._attr_name = f"{device.name} {name}"
            self._attr_unique_id = f"{device.id_}-{sensor}"
        else:
            self._attr_name = f"{device.name} {group[0]} {name}"
            self._attr_unique_id = f"{device.id_}-{group[1]}-{sensor}"

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

    def _value(self, attr):
        if self._groupid is None:
            return self._device.status.__dict__[attr]
        else:
            return self._device.status.__dict__[self._groupid].__dict__[attr]

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._value(self._sensor)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        if self._extra_attributes is not None:
            return {attr: self._value(attr) for attr in self._extra_attributes}
        return None

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

"""Garo Wallbox integration implementation"""
import logging
import time
from datetime import timedelta
from enum import Enum

from homeassistant.util import Throttle
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    GARO_PRODUCT_MAP,
    VOLTAGE,
    LOCAL_METER_PATH,
    GROUP_METER_PATH,
    GROUP101_METER_PATH,
    CURRENT_DIVIDER,
)


def current_milli_time():
    """Get the current time in milliseconds."""
    return int(round(time.time() * 1000))


MODE_ON, MODE_OFF, MODE_SCHEMA = ("ALWAYS_ON", "ALWAYS_OFF", "SCHEMA")
STATUS_CHANGING, STATUS_NOT_CONNECTED, STATUS_CONNECTED, STATUS_SEARCH_COMM = (
    "CHANGING",
    "NOT_CONNECTED",
    "CONNECTED",
    "SEARCH_COMM",
)

HEADER_JSON = {"content-type": "application/json; charset=utf-8"}

_LOGGER = logging.getLogger(__name__)


class Mode(Enum):
    """Garo Wallbox mode."""

    ON = MODE_ON
    OFF = MODE_OFF
    SCHEMA = MODE_SCHEMA


class Status(Enum):
    """Garo Wallbox status"""

    CHANGING = "CHANGING"
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTED = "CONNECTED"
    SEARCH_COMM = "SEARCH_COMM"
    RCD_FAULT = "RCD_FAULT"
    CHARGING = "CHARGING"
    CHARGING_PAUSED = "CHARGING_PAUSED"
    CHARGING_FINISHED = "CHARGING_FINISHED"
    CHARGING_CANCELLED = "CHARGING_CANCELLED"
    DISABLED = "DISABLED"
    OVERHEAT = "OVERHEAT"
    CRITICAL_TEMPERATURE = "CRITICAL_TEMPERATURE"
    INITIALIZATION = "INITIALIZATION"
    CABLE_FAULT = "CABLE_FAULT"
    LOCK_FAULT = "LOCK_FAULT"
    CONTACTOR_FAULT = "CONTACTOR_FAULT"
    VENT_FAULT = "VENT_FAULT"
    DC_ERROR = "DC_ERROR"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


class GaroDevice:
    """Class representing a Garo device"""

    def __init__(self, host, name, session) -> None:
        self.id_ = None
        self.info = None
        self.host = host
        self.name = name
        self.meter = None
        self._status = None
        self._session = session
        self._pre_v1_3 = False

    async def init(self):
        """Initialise the Garo Wallbox integration."""
        await self.async_get_info()
        self.id_ = f"garo_{self.info.serial}"
        if self.name is None:
            self.name = f"{self.info.model} ({self.host})"
        if self.info.meter_path:
            # Energy meter was found
            self.meter = MeterDevice(self)
            await self.meter.init()
        await self.async_update()

    @property
    def status(self):
        """Get the current status of the Garo Wallbox."""
        return self._status

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.id_)},
            manufacturer="Garo",
            model=self.info.model,
            name=self.name,
        )

    @property
    def chargers(self):
        """Return a list of tuple with charger name and charger id"""
        return [
            ("Main Charger", "main_charger"),
            ("Twin Charger", "twin_charger"),
        ][: self.info.nof_chargers]

    def _request(self, parameter_list):
        pass

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Fetch Garo Wallbox status."""
        await self._do_update()

    async def _do_update(self):
        response = await self._session.request(
            method="GET", url=self.__get_url("status", True)
        )
        if response.status != 200 and not self._pre_v1_3:
            self._pre_v1_3 = True
            _LOGGER.info("Switching to pre v1.3.1 endpoint")
            response = await self._session.request(
                method="GET", url=self.__get_url("status", True)
            )

        response_json = await response.json()
        self._status = GaroStatus(response_json, self)

    async def async_get_info(self):
        """Fetch Garo Wallbox configuration information."""
        response = await self._session.request(
            method="GET", url=self.__get_url("config", True)
        )
        _LOGGER.info("Response %s", response)
        if response.status != 200 and not self._pre_v1_3:
            self._pre_v1_3 = True
            _LOGGER.info("Switching to pre v1.3.1 endpoint")
            response = await self._session.request(
                method="GET", url=self.__get_url("config", True)
            )

        response_json = await response.json()
        self.info = GaroDeviceInfo(response_json)

    async def set_mode(self, mode: Mode):
        """Set the current Garo Wallbox mode."""
        if self._pre_v1_3:
            response = await self._session.post(
                self.__get_url("mode"), data=mode.value, headers=HEADER_JSON
            )
        else:
            response = await self._session.post(
                self.__get_url(f"mode/{mode.value}"), headers=HEADER_JSON
            )
        await response.text()
        await self._do_update()

    async def set_current_limit(self, limit):
        """Set the current Garo Wallbox charging current limit."""
        response = await self._session.request(
            method="GET", url=self.__get_url("config", True)
        )
        response_json = await response.json()
        response_json["reducedCurrentIntervals"] = [
            {
                "chargeLimit": str(limit),
                "schemaId": 1,
                "start": "00:00:00",
                "stop": "24:00:00",
                "weekday": 8,
            }
        ]
        # _LOGGER.warning(f'Set limit: {response_json}')
        response = await self._session.post(
            self.__get_url("config"), json=response_json, headers=HEADER_JSON
        )
        await response.text()
        await self._do_update()

    def __get_url(self, action, add_tick=False):
        tick = "" if not add_tick else f"?_={current_milli_time()}"
        if self._pre_v1_3:
            return f"http://{self.host}:2222/rest/chargebox/{action}{tick}"
        return f"http://{self.host}:8080/servlet/rest/chargebox/{action}{tick}"

    async def get_json_response(self, action, add_tick):
        url = self.__get_url(action, add_tick)
        response = await self._session.request(method="GET", url=url)
        json_response = await response.json()
        return json_response


class GaroStatus:
    """Class representing Garo status."""

    def __init__(self, response, device) -> None:
        self.mode = Mode(response["mode"])

        self.temperature = response["currentTemperature"]
        self.temperature_warning = device.info.temperature_warning
        self.temperature_cutoff = device.info.temperature_cutoff

        self.current_limit = response["currentLimit"]
        self.factory_current_limit = response["factoryCurrentLimit"]
        self.switch_current_limit = response["switchCurrentLimit"]

        self.power_mode = response["powerMode"]

        if "mainCharger" in response:
            self.main_charger = GaroChargerStatus(
                response["mainCharger"], device.status and device.status.main_charger
            )
        else:
            self.main_charger = GaroChargerStatus(
                response, device.status and device.status.main_charger
            )
        if "twinCharger" in response:
            self.twin_charger = GaroChargerStatus(
                response["twinCharger"], device.status and device.status.twin_charger
            )


class GaroChargerStatus:
    """Class representing Garo charger status."""

    def __init__(self, response, prev_status) -> None:
        self.status = Status(response["connector"])
        self.status_descr = _status_to_descr(self.status)
        self.nr_of_phases = response["nrOfPhases"]

        self.charge_status = response["chargeStatus"]

        self.charging_current = max(0, response["currentChargingCurrent"] / 1000)
        self.pilot_level = response["pilotLevel"]
        self.min_current_limit = response["minCurrentLimit"]

        self.charging_power = max(0, response["currentChargingPower"])
        if self.charging_power > 32000:
            self.charging_power = 0

        last_reading = response["accEnergy"]
        if prev_status is not None and last_reading - prev_status.acc_energy > 500000:
            last_reading = prev_status.acc_energy

        self.acc_energy = last_reading

        self.session_acc_energy = response["accSessionEnergy"]
        self.session_start_energy = response["sessionStartValue"]
        self.session_start_time = response["sessionStartTime"]
        self.session_duration = response["accSessionMillis"] / 1000

        self.load_balancing = response["loadBalanced"]
        self.load_balanceing_phase = response["phase"]

        # TODO Can this one be controlled?
        self.cable_lock_mode = response["cableLockMode"]

        # TODO As sub to status? What does it mean? Check manual
        self.dip_switch_setting = response["dipSwitchSettings"]


def _status_to_descr(status):
    """Return status as a string."""
    return {
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
    }.get(status, "Unknown")


class GaroDeviceInfo:
    """Class representing Garo information."""

    def __init__(self, response) -> None:
        self.temperature_warning = (response["warningTemperature"],)
        self.temperature_cutoff = (response["cutoffTemperature"],)

        self.serial = response["serialNumber"]
        self.product_id = response["productId"]
        self.model = GARO_PRODUCT_MAP[int(self.product_id)]
        self.max_current = response["maxChargeCurrent"]

        self.nof_chargers = len(response["slaveList"])

        if response.get("localLoadBalanced"):
            self.meter_path = LOCAL_METER_PATH
        elif response.get("groupLoadBalanced"):
            self.meter_path = GROUP_METER_PATH
        elif response.get("groupLoadBalanced101"):
            self.meter_path = GROUP101_METER_PATH
        else:
            self.meter_path = None


class MeterDevice:
    def __init__(self, device):
        self.main_device = device
        self.name = device.name + " meter"
        self.meter_action = f"meterinfo/{device.info.meter_path}"
        self.status = None
        self.id_ = None

    async def init(self):
        await self.async_update()
        self.id_ = "garo_{}".format(self.status.serial)

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "identifiers": {(DOMAIN, self.id_)},
            "manufacturer": "Garo",
            "model": self.status.type,
            "name": self.name,
            "via_device": (DOMAIN, self.main_device.id_),
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        json = await self.main_device.get_json_response(self.meter_action, True)
        self.status = MeterStatus(json)


class MeterStatus:
    def __init__(self, response):
        self.serial = response["meterSerial"]
        self.type = response["type"]
        # TODO, use current divider based on firmware version
        self.phase1_current = response["phase1Current"] / CURRENT_DIVIDER
        self.phase2_current = response["phase2Current"] / CURRENT_DIVIDER
        self.phase3_current = response["phase3Current"] / CURRENT_DIVIDER
        current = self.phase1_current + self.phase2_current + self.phase3_current
        self.power = int(round(current * VOLTAGE, -1))
        self.acc_energy_k = round(response["accEnergy"] / 1000, 1)
        _LOGGER.debug(self.__dict__)

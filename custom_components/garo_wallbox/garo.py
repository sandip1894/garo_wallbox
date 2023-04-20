"""Garo Wallbox integration implementation"""
import logging
import time
from datetime import timedelta
from enum import Enum

from homeassistant.util import Throttle
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, GARO_PRODUCT_MAP


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
        self._status = None
        self._session = session
        self._pre_v1_3 = False

    async def init(self):
        """Initialise the Garo Wallbox integration."""
        await self.async_get_info()
        self.id_ = f"garo_{self.info.serial}"
        if self.name is None:
            self.name = f"{self.info.model} ({self.host})"
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
        self._status = GaroStatus(response_json, self._status)

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


class GaroStatus:
    """Class representing Daro status."""

    def __init__(self, response, prev_status) -> None:
        self.ocpp_state = response["ocppState"]
        self.free_charging = response["freeCharging"]
        self.ocpp_connection_state = response["ocppConnectionState"]
        self.status = Status(response["connector"])
        self.mode = Mode(response["mode"])
        self.current_limit = response["currentLimit"]
        self.factory_current_limit = response["factoryCurrentLimit"]
        self.switch_current_limit = response["switchCurrentLimit"]
        self.power_mode = response["powerMode"]
        self.current_charging_current = max(
            0, response["currentChargingCurrent"] / 1000
        )
        self.current_charging_power = max(0, response["currentChargingPower"])
        if self.current_charging_power > 32000:
            self.current_charging_power = 0
        self.acc_session_energy = response["accSessionEnergy"]
        last_reading = response["latestReading"]
        if (
            prev_status is not None
            and last_reading - prev_status.latest_reading > 500000
        ):
            last_reading = prev_status.latest_reading

        self.latest_reading = last_reading
        self.latest_reading_k = max(0, last_reading / 1000)
        self.current_temperature = response["currentTemperature"]
        self.pilot_level = response["pilotLevel"]
        self.session_start_value = response["sessionStartValue"]
        self.nr_of_phases = response["nrOfPhases"]


class GaroDeviceInfo:
    """Class representing Garo information."""

    def __init__(self, response) -> None:
        self.serial = response["serialNumber"]
        self.product_id = response["productId"]
        self.model = GARO_PRODUCT_MAP[int(self.product_id)]
        self.max_current = response["maxChargeCurrent"]

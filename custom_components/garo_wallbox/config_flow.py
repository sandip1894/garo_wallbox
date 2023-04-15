"""Config flow for the Garo Wallbox platform."""
import asyncio
import logging

from aiohttp import ClientError
from async_timeout import timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME

from .garo import GaroDevice

from .const import KEY_IP, TIMEOUT

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register("garo_wallbox")
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def _create_entry(self, host, name):
        """Register new entry."""
        # Check if ip already is registered
        for entry in self._async_current_entries():
            if entry.data[KEY_IP] == host:
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=host, data={CONF_HOST: host, CONF_NAME: name}
        )

    async def _create_device(self, host, name):
        """Create device."""

        try:
            device = GaroDevice(
                host, name, self.hass.helpers.aiohttp_client.async_get_clientsession()
            )
            with timeout(TIMEOUT):
                await device.init()
        except asyncio.TimeoutError:
            return self.async_abort(reason="device_timeout")
        except ClientError:
            _LOGGER.exception("ClientError")
            return self.async_abort(reason="device_fail")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error creating device")
            return self.async_abort(reason="device_fail")

        return await self._create_entry(host, name)

    async def async_step_user(self, user_input=None):
        """User initiated config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_HOST): str, vol.Optional(CONF_NAME): str}
                ),
            )
        return await self._create_device(
            user_input[CONF_HOST], user_input.get(CONF_NAME)
        )

    async def async_step_import(self, user_input):
        """Import a config entry."""
        host = user_input.get(CONF_HOST)
        if not host:
            return await self.async_step_user()
        return await self._create_device(host, user_input[CONF_NAME])

    async def async_step_discovery(self, discovery_info):
        """Initialize step from discovery."""
        _LOGGER.info("Discovered device: %s", discovery_info)
        return await self._create_entry(discovery_info[KEY_IP], None)

"""Config flow for Sonic."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sonic import InvalidCredentialsError, Client, RequestError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})
USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class SonicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Sonic Config Flow."""

    _data_schema = USER_SCHEMA
    _username: str

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Define the login user step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=self._data_schema,
            )

        username: str = user_input[CONF_USERNAME]
        await self.async_set_unique_id(username.lower())
        self._abort_if_unique_id_configured()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        return await self._try_connect_sonic("user", None, username, password)

    async def async_step_reauth(self, data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self._data_schema = REAUTH_SCHEMA
        self._username = data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle re-auth completion."""
        placeholders = {"username": self._username}
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self._data_schema,
                description_placeholders=placeholders,
            )

        password = user_input[CONF_PASSWORD]
        return await self._try_connect_sonic(
            "reauth_confirm", placeholders, self._username, password
        )

    async def _try_connect_sonic(
        self, step_id, placeholders: dict[str, str] | None, username: str, password: str
    ) -> FlowResult:
        session = aiohttp_client.async_get_clientsession(self.hass)

        api = Client(session)
        errors = {}

        try:
            await api.async_login(username, password)
        except InvalidCredentialsError:
            errors["base"] = "invalid_auth"
        except RequestError:
            errors["base"] = "service_unavailable_error"
        except Exception:  # pylint: disable=broad-except
            errors["base"] = "unknown_auth_error"
        else:
            data = {"username": username, "password": password}
            existing_entry = await self.async_set_unique_id(username.lower())
            if existing_entry:
                self.hass.config_entries.async_update_entry(existing_entry, data=data)
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            return self.async_create_entry(
                title="Sonic",
                data=data,
            )

        return self.async_show_form(
            step_id=step_id,
            data_schema=self._data_schema,
            description_placeholders=placeholders,
            errors=errors,
        )

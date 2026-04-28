"""Config flow: paste refresh token (extracted via mitm) until OAuth flow built."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KarcherAPI
from .auth import KarcherAuth
from .const import CONF_REFRESH_TOKEN, CONF_USER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_REFRESH_TOKEN): str})


class KarcherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup. v0.1: paste refresh token; later: full OAuth via auth.kaercher.com."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            auth = KarcherAuth(session, user_input[CONF_REFRESH_TOKEN])
            try:
                await auth.get_id_token()
                api = KarcherAPI(session, auth)
                profile = await api.get_profile()
                user_id = profile["id"]
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Auth validation failed: %s", err)
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=profile.get("email") or f"Kärcher ({user_id[:8]})",
                    data={
                        CONF_REFRESH_TOKEN: await auth.get_refresh_token(),
                        CONF_USER_ID: user_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={
                "info": (
                    "Paste a Cognito refresh_token captured from the Kärcher app. "
                    "OAuth login flow with ReCaptcha not yet implemented."
                )
            },
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-auth when refresh token expires."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            auth = KarcherAuth(session, user_input[CONF_REFRESH_TOKEN])
            try:
                await auth.get_id_token()
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Re-auth validation failed: %s", err)
                errors["base"] = "invalid_auth"
            else:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                if entry:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            CONF_REFRESH_TOKEN: await auth.get_refresh_token(),
                        },
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

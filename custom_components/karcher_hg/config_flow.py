"""Config flow: Browser OAuth (user solves captcha) or paste refresh token."""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from typing import Any
from urllib.parse import parse_qs, urlparse

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KarcherAPI
from .auth import KarcherAuth
from .const import (
    COGNITO_AUTHORIZE_URL,
    COGNITO_CLIENT_ID,
    COGNITO_HOSTED_BASE,
    COGNITO_TOKEN_URL,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    DOMAIN,
    IDP_NAME,
    OAUTH_REDIRECT_URI,
)

_LOGGER = logging.getLogger(__name__)

TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_REFRESH_TOKEN): str})
CALLBACK_SCHEMA = vol.Schema({vol.Required("callback_url"): str})


def _pkce_verifier() -> str:
    """Generate PKCE code_verifier (43-128 URL-safe chars)."""
    return secrets.token_urlsafe(32)


def _pkce_challenge(verifier: str) -> str:
    """S256 code_challenge from code_verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _build_authorize_url(code_challenge: str) -> str:
    """Build Cognito authorize URL with PKCE + IdP hint."""
    return (
        f"{COGNITO_AUTHORIZE_URL}"
        f"?client_id={COGNITO_CLIENT_ID}"
        f"&redirect_uri={OAUTH_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid+profile+email"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&identity_provider={IDP_NAME}"
    )


def _extract_code(url: str) -> str | None:
    """Extract ?code= from callback URL (custom scheme or full URL)."""
    try:
        parsed = urlparse(url)
        codes = parse_qs(parsed.query).get("code")
        return codes[0] if codes else None
    except Exception:  # noqa: BLE001
        return None


class KarcherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Setup: Browser OAuth or paste refresh token."""

    VERSION = 1

    def __init__(self) -> None:
        """Init flow state."""
        self._code_verifier: str | None = None
        self._auth_url: str | None = None

    # ── Menu ─────────────────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose login method."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["browser", "token"],
        )

    # ── Browser OAuth (user solves captcha in real browser) ──────

    async def async_step_browser(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show auth URL → user pastes callback URL with code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Parse callback URL for authorization code
            code = _extract_code(user_input["callback_url"])
            if not code:
                errors["base"] = "no_code"
            else:
                session = async_get_clientsession(self.hass)
                try:
                    refresh_token = await self._exchange_code(session, code)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.error("Token exchange failed: %s", err)
                    errors["base"] = "token_exchange_failed"
                else:
                    return await self._finish_setup(session, refresh_token)

        # Generate PKCE pair + authorize URL (on first show or after error)
        if self._code_verifier is None:
            self._code_verifier = _pkce_verifier()
            challenge = _pkce_challenge(self._code_verifier)
            self._auth_url = _build_authorize_url(challenge)

        return self.async_show_form(
            step_id="browser",
            data_schema=CALLBACK_SCHEMA,
            errors=errors,
            description_placeholders={"auth_url": self._auth_url},
        )

    async def _exchange_code(
        self, session: aiohttp.ClientSession, code: str
    ) -> str:
        """Exchange authorization code for Cognito tokens via PKCE."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "client_id": COGNITO_CLIENT_ID,
            "code_verifier": self._code_verifier,
        }
        async with session.post(
            COGNITO_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as resp:
            result = await resp.json(content_type=None)
            if resp.status != 200:
                raise RuntimeError(
                    f"Cognito token exchange failed: {resp.status} "
                    f"{result.get('error', result)}"
                )
        refresh_token = result.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("No refresh_token in Cognito response")
        return refresh_token

    # ── Token paste (fallback) ───────────────────────────────────

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Fallback: paste refresh token from app/mitmproxy."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            auth = KarcherAuth(session, user_input[CONF_REFRESH_TOKEN])
            try:
                await auth.get_id_token()
                refresh_token = await auth.get_refresh_token()
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Token validation failed: %s", err)
                errors["base"] = "invalid_auth"
            else:
                return await self._finish_setup(session, refresh_token)

        return self.async_show_form(
            step_id="token",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
        )

    # ── Shared: validate + create entry ──────────────────────────

    async def _finish_setup(
        self, session: aiohttp.ClientSession, refresh_token: str
    ) -> ConfigFlowResult:
        """Validate token and create config entry."""
        auth = KarcherAuth(session, refresh_token)
        await auth.get_id_token()
        api = KarcherAPI(session, auth)
        profile = await api.get_profile()
        user_id = profile["id"]

        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=profile.get("email") or f"Kärcher ({user_id[:8]})",
            data={
                CONF_REFRESH_TOKEN: await auth.get_refresh_token(),
                CONF_USER_ID: user_id,
            },
        )

    # ── Re-auth (token expired) ──────────────────────────────────

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-auth: choose browser or token paste."""
        return self.async_show_menu(
            step_id="reauth_confirm",
            menu_options=["reauth_browser", "reauth_token"],
        )

    async def async_step_reauth_browser(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-auth via browser OAuth."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = _extract_code(user_input["callback_url"])
            if not code:
                errors["base"] = "no_code"
            else:
                session = async_get_clientsession(self.hass)
                try:
                    refresh_token = await self._exchange_code(session, code)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.error("Re-auth token exchange failed: %s", err)
                    errors["base"] = "token_exchange_failed"
                else:
                    return await self._finish_reauth(session, refresh_token)

        if self._code_verifier is None:
            self._code_verifier = _pkce_verifier()
            challenge = _pkce_challenge(self._code_verifier)
            self._auth_url = _build_authorize_url(challenge)

        return self.async_show_form(
            step_id="reauth_browser",
            data_schema=CALLBACK_SCHEMA,
            errors=errors,
            description_placeholders={"auth_url": self._auth_url},
        )

    async def async_step_reauth_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-auth: paste new refresh token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            auth = KarcherAuth(session, user_input[CONF_REFRESH_TOKEN])
            try:
                await auth.get_id_token()
                refresh_token = await auth.get_refresh_token()
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Re-auth validation failed: %s", err)
                errors["base"] = "invalid_auth"
            else:
                return await self._finish_reauth(session, refresh_token)

        return self.async_show_form(
            step_id="reauth_token",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
        )

    async def _finish_reauth(
        self, session: aiohttp.ClientSession, refresh_token: str
    ) -> ConfigFlowResult:
        """Complete re-auth by updating the config entry."""
        auth = KarcherAuth(session, refresh_token)
        await auth.get_id_token()
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

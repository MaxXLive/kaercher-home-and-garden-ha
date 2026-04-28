"""Kärcher Home & Garden integration setup."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KarcherAPI
from .auth import KarcherAuth
from .const import CONF_REFRESH_TOKEN, CONF_USER_ID, DOMAIN
from .coordinator import KarcherCoordinator
from .iot import KarcherIoT

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.VACUUM,
    Platform.CAMERA,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kärcher H&G from a config entry."""
    session = async_get_clientsession(hass)
    auth = KarcherAuth(session, entry.data[CONF_REFRESH_TOKEN])

    # Eager: refresh once so config validates and we get a stable refresh_token
    await auth.get_id_token()
    new_rt = await auth.get_refresh_token()
    if new_rt != entry.data[CONF_REFRESH_TOKEN]:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_REFRESH_TOKEN: new_rt}
        )

    api = KarcherAPI(session, auth)
    iot = KarcherIoT(session, auth)
    coordinator = KarcherCoordinator(hass, auth, api, iot, entry.data[CONF_USER_ID])
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow user to remove old/orphaned devices from the integration."""
    return True

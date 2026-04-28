"""Vacuum entity for the RCV robot — commands enabled, verified payloads."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CLEAN_TYPE_GLOBAL,
    CMD_FIND_DEVICE,
    CMD_SET_ROOM_CLEAN,
    CMD_START_RECHARGE,
    CTR_PAUSE,
    CTR_START,
    CTR_STOP,
    DOMAIN,
)
from .coordinator import KarcherCoordinator
from .entity import KarcherEntity

_LOGGER = logging.getLogger(__name__)

# Robot vacuum part numbers we know about
ROBOT_PART_NUMBERS = {
    "1.269-640.0",  # RCV 5 with mopping
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: KarcherCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[KarcherVacuum] = []
    for dm_id, dev in (coord.data or {}).items():
        if dev.part_number in ROBOT_PART_NUMBERS:
            entities.append(KarcherVacuum(coord, dm_id))
    async_add_entities(entities)


class KarcherVacuum(KarcherEntity, StateVacuumEntity):
    """Robot vacuum with full command support."""

    _attr_translation_key = "robot"
    _attr_name = None  # use device name

    def __init__(self, coord: KarcherCoordinator, dm_id: str) -> None:
        super().__init__(coord, dm_id)
        self._attr_unique_id = f"{dm_id}_vacuum"
        self._attr_supported_features = (
            VacuumEntityFeature.STATE
            | VacuumEntityFeature.BATTERY
            | VacuumEntityFeature.START
            | VacuumEntityFeature.STOP
            | VacuumEntityFeature.PAUSE
            | VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.LOCATE
        )

    @property
    def battery_level(self) -> int | None:
        d = self.device
        return d.battery_level if d else None

    @property
    def activity(self) -> VacuumActivity | None:
        d = self.device
        if not d:
            return None
        if not d.is_online:
            return VacuumActivity.IDLE

        # state.status: 0=idle, 1=cleaning, 2=paused, 3=charging(?), 5=exploring(?)
        # state.fault: 0=ok, >0=error
        # state.charge_state: 0=not charging, >0=charging
        if d.fault and d.fault != 0:
            return VacuumActivity.ERROR
        if d.status == 1:
            return VacuumActivity.CLEANING
        if d.status == 2:
            return VacuumActivity.PAUSED
        if d.charge_state and d.charge_state != 0:
            return VacuumActivity.DOCKED
        if d.status == 0:
            return VacuumActivity.IDLE
        return VacuumActivity.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.device
        if not d:
            return {}
        attrs: dict[str, Any] = {}
        if d.wind is not None:
            attrs["suction_level"] = d.wind
        if d.water is not None:
            attrs["water_level"] = d.water
        if d.map_name:
            attrs["map_name"] = d.map_name
        if d.tank_state is not None:
            attrs["tank_state"] = d.tank_state
        if d.cloth_state is not None:
            attrs["cloth_state"] = d.cloth_state
        return attrs

    # ── Commands (verified payloads from MITM capture) ──

    async def _cmd(self, command: str, payload: dict[str, Any] | None = None) -> None:
        d = self.device
        if not d:
            raise HomeAssistantError("Device unavailable")
        await self.coordinator.api.send_command(d.dm_id, command, payload)
        await self.coordinator.async_request_refresh()

    async def async_start(self) -> None:
        """Start global clean (all rooms)."""
        await self._cmd(CMD_SET_ROOM_CLEAN, {
            "cleanType": CLEAN_TYPE_GLOBAL,
            "ctrValue": CTR_START,
            "roomIds": [],
        })

    async def async_pause(self) -> None:
        await self._cmd(CMD_SET_ROOM_CLEAN, {
            "cleanType": CLEAN_TYPE_GLOBAL,
            "ctrValue": CTR_PAUSE,
            "roomIds": [],
        })

    async def async_stop(self, **_: Any) -> None:
        await self._cmd(CMD_SET_ROOM_CLEAN, {
            "cleanType": CLEAN_TYPE_GLOBAL,
            "ctrValue": CTR_STOP,
            "roomIds": [],
        })

    async def async_return_to_base(self, **_: Any) -> None:
        await self._cmd(CMD_START_RECHARGE)

    async def async_locate(self, **_: Any) -> None:
        await self._cmd(CMD_FIND_DEVICE)

    async def async_clean_rooms(self, room_ids: list[int]) -> None:
        """Start cleaning specific rooms by ID."""
        await self._cmd(CMD_SET_ROOM_CLEAN, {
            "cleanType": CLEAN_TYPE_GLOBAL,
            "ctrValue": CTR_START,
            "roomIds": room_ids,
        })

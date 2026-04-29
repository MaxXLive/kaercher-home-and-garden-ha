"""Vacuum entity for the RCV robot — commands enabled, verified payloads."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from .const import (
    CLEAN_TYPE_GLOBAL,
    CMD_FIND_DEVICE,
    CMD_SET_PREFERENCE,
    CMD_SET_ROOM_CLEAN,
    CMD_START_RECHARGE,
    CTR_PAUSE,
    CTR_START,
    CTR_STOP,
    DOMAIN,
    SWEEP_TYPE_MOP_ONLY,
    SWEEP_TYPE_VAC_THEN_MOP,
    SWEEP_TYPE_VACUUM,
    SWEEP_TYPE_VACUUM_MOP,
    decode_fault,
)
from .coordinator import KarcherCoordinator
from .entity import KarcherEntity

_LOGGER = logging.getLogger(__name__)

# Robot vacuum part numbers we know about
ROBOT_PART_NUMBERS = {
    "1.269-640.0",  # RCV 5 with mopping
}

# Sweep-type friendly names (DE)
SWEEP_TYPE_NAMES = {
    SWEEP_TYPE_VACUUM: "Nur Saugen",
    SWEEP_TYPE_VACUUM_MOP: "Saugen & Wischen",
    SWEEP_TYPE_MOP_ONLY: "Nur Wischen",
    SWEEP_TYPE_VAC_THEN_MOP: "Erst Saugen, dann Wischen",
}

# Service schemas
SERVICE_CLEAN_ROOMS = "clean_rooms"
SERVICE_SET_SWEEP_TYPE = "set_sweep_type"

SCHEMA_CLEAN_ROOMS = {
    vol.Required("room_ids"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional("sweep_type"): vol.In([0, 1, 2, 3]),
}
SCHEMA_SET_SWEEP_TYPE = {
    vol.Required("sweep_type"): vol.In([0, 1, 2, 3]),
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

    # Register custom services
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CLEAN_ROOMS,
        SCHEMA_CLEAN_ROOMS,
        "async_clean_rooms",
    )
    platform.async_register_entity_service(
        SERVICE_SET_SWEEP_TYPE,
        SCHEMA_SET_SWEEP_TYPE,
        "async_set_sweep_type",
    )


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

        # RobotStatus enum (from decompiled app):
        #  0=sleep, 1=standBy, 2=pause, 3=recharging, 4=charging,
        #  5=sweeping, 6=sweepingAndMopping, 7=mopping, 8=upgrading,
        #  9=cleaning, 10=airDrying, 11=dustCollecting, 12=buildingMap, 13=cuttingHair
        #
        # Fault codes: 0=none. Use decode_fault() to check if blocking.
        # Non-blocking faults (snack in app, e.g. 2103) don't override status.
        fault_desc, fault_blocking = decode_fault(d.fault)
        if fault_blocking:
            return VacuumActivity.ERROR
        s = d.status
        if s in (5, 6, 7, 9, 12, 13):  # sweeping/sweepMop/mopping/cleaning/buildingMap/cuttingHair
            return VacuumActivity.CLEANING
        if s == 2:  # pause
            return VacuumActivity.PAUSED
        if s == 3:  # recharging (returning to dock)
            return VacuumActivity.RETURNING
        if s in (4, 10, 11):  # charging/airDrying/dustCollecting
            return VacuumActivity.DOCKED
        if s in (0, 1):  # sleep/standBy
            if d.charge_state and d.charge_state != 0:
                return VacuumActivity.DOCKED
            return VacuumActivity.IDLE
        if s == 8:  # upgrading
            return VacuumActivity.DOCKED
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
        if d.status is not None:
            attrs["raw_status"] = d.status
        if d.work_mode is not None:
            attrs["work_mode"] = d.work_mode
        if d.sweep_type is not None:
            attrs["sweep_type"] = d.sweep_type
            attrs["sweep_type_name"] = SWEEP_TYPE_NAMES.get(d.sweep_type, f"Unbekannt ({d.sweep_type})")
        if d.charge_state is not None:
            attrs["charge_state"] = d.charge_state
        # Decoded fault — always present
        fault_desc, fault_blocking = decode_fault(d.fault)
        attrs["fault_code"] = d.fault if d.fault else 0
        attrs["fault_description"] = fault_desc
        attrs["fault_blocking"] = fault_blocking
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

    async def async_clean_rooms(self, room_ids: list[int], sweep_type: int | None = None) -> None:
        """Start cleaning specific rooms by ID, optionally set cleaning mode first."""
        if sweep_type is not None:
            await self._cmd(CMD_SET_PREFERENCE, {"sweep_type": sweep_type})
        await self._cmd(CMD_SET_ROOM_CLEAN, {
            "cleanType": CLEAN_TYPE_GLOBAL,
            "ctrValue": CTR_START,
            "roomIds": room_ids,
        })

    async def async_set_sweep_type(self, sweep_type: int) -> None:
        """Set cleaning mode: 0=vacuum, 1=vacuum+mop, 2=mop only, 3=vacuum then mop."""
        await self._cmd(CMD_SET_PREFERENCE, {"sweep_type": sweep_type})

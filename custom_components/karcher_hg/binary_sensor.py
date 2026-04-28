"""Binary sensors: online, fault, low-battery."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KarcherCoordinator, KarcherDevice
from .entity import KarcherEntity


@dataclass(frozen=True, kw_only=True)
class KarcherBinaryDesc(BinarySensorEntityDescription):
    value: Callable[[KarcherDevice], bool | None]


BINARY_SENSORS: tuple[KarcherBinaryDesc, ...] = (
    KarcherBinaryDesc(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value=lambda d: d.is_online,
    ),
    KarcherBinaryDesc(
        key="fault",
        translation_key="fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda d: bool(d.fault) if d.fault is not None else None,
    ),
    KarcherBinaryDesc(
        key="provisioned",
        translation_key="provisioned",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda d: d.is_provisioned,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: KarcherCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[KarcherBinarySensor] = []
    for dm_id in coord.data or {}:
        for desc in BINARY_SENSORS:
            entities.append(KarcherBinarySensor(coord, dm_id, desc))
    async_add_entities(entities)


class KarcherBinarySensor(KarcherEntity, BinarySensorEntity):
    entity_description: KarcherBinaryDesc

    def __init__(
        self, coord: KarcherCoordinator, dm_id: str, desc: KarcherBinaryDesc
    ) -> None:
        # Online sensor must remain available even when device is offline
        super().__init__(coord, dm_id)
        self.entity_description = desc
        self._attr_unique_id = f"{dm_id}_{desc.key}"

    @property
    def available(self) -> bool:
        # Online sensor must report regardless of online state
        if self.entity_description.key == "online":
            return self.coordinator.last_update_success and self.device is not None
        return super().available

    @property
    def is_on(self) -> bool | None:
        d = self.device
        return self.entity_description.value(d) if d else None

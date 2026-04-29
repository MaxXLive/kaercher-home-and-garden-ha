"""Sensor entities: battery, consumables, cleaning stats, firmware, wifi."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, decode_fault
from .coordinator import KarcherCoordinator, KarcherDevice
from .entity import KarcherEntity


@dataclass(frozen=True, kw_only=True)
class KarcherSensorDesc(SensorEntityDescription):
    value: Callable[[KarcherDevice], Any]


SENSORS: tuple[KarcherSensorDesc, ...] = (
    KarcherSensorDesc(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda d: d.battery_level,
    ),
    KarcherSensorDesc(
        key="hepa_filter",
        translation_key="hepa_filter",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.hypa_life,
    ),
    KarcherSensorDesc(
        key="main_brush",
        translation_key="main_brush",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.main_brush_life,
    ),
    KarcherSensorDesc(
        key="side_brush",
        translation_key="side_brush",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.side_brush_life,
    ),
    KarcherSensorDesc(
        key="mop",
        translation_key="mop",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.mop_life,
    ),
    KarcherSensorDesc(
        key="cleaning_time",
        translation_key="cleaning_time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        value=lambda d: d.cleaning_time,
    ),
    KarcherSensorDesc(
        key="cleaning_area",
        translation_key="cleaning_area",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value=lambda d: d.cleaning_area,
    ),
    KarcherSensorDesc(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda d: int(d.wifi_rssi) if d.wifi_rssi else None,
    ),
    KarcherSensorDesc(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda d: d.firmware,
    ),
    KarcherSensorDesc(
        key="fault_code",
        translation_key="fault_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: decode_fault(d.fault)[0] if d.fault and d.fault != 0 else "Kein Fehler",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: KarcherCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[KarcherSensor] = []
    for dm_id in coord.data or {}:
        for desc in SENSORS:
            entities.append(KarcherSensor(coord, dm_id, desc))
    async_add_entities(entities)


class KarcherSensor(KarcherEntity, SensorEntity):
    entity_description: KarcherSensorDesc

    def __init__(
        self, coord: KarcherCoordinator, dm_id: str, desc: KarcherSensorDesc
    ) -> None:
        super().__init__(coord, dm_id)
        self.entity_description = desc
        self._attr_unique_id = f"{dm_id}_{desc.key}"

    @property
    def native_value(self) -> Any:
        d = self.device
        return self.entity_description.value(d) if d else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "fault_code":
            return None
        d = self.device
        if not d:
            return None
        code = d.fault if d.fault else 0
        _, blocking = decode_fault(d.fault)
        return {"raw_code": code, "blocking": blocking}

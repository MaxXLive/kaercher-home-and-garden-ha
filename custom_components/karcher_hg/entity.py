"""Base entity: each Kärcher device → one HA Device with shared device_info."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KarcherCoordinator, KarcherDevice


class KarcherEntity(CoordinatorEntity[KarcherCoordinator]):
    """Base entity scoped to one device (dmId)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KarcherCoordinator, dm_id: str) -> None:
        super().__init__(coordinator)
        self._dm_id = dm_id

    @property
    def device(self) -> KarcherDevice | None:
        return self.coordinator.data.get(self._dm_id) if self.coordinator.data else None

    @property
    def available(self) -> bool:
        d = self.device
        return super().available and d is not None and d.is_online

    @property
    def device_info(self) -> DeviceInfo:
        d = self.device
        return DeviceInfo(
            identifiers={(DOMAIN, self._dm_id)},
            manufacturer="Kärcher",
            model=d.part_number if d else None,
            name=(d.name if d and d.name else None) or f"Kärcher {self._dm_id[:6]}",
            sw_version=d.firmware if d else None,
            serial_number=d.serial_number if d else None,
        )

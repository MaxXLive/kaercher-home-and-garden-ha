"""DataUpdateCoordinator: polls device list + all named shadows."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KarcherAPI
from .auth import KarcherAuth
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, SHADOW_MAPS
from .iot import KarcherIoT

_LOGGER = logging.getLogger(__name__)


@dataclass
class KarcherDevice:
    # ── DM metadata ──
    dm_id: str
    device_id: str
    part_number: str
    serial_number: str
    vendor_id: str
    product_id: str
    user_id: str
    is_online: bool
    is_provisioned: bool

    # ── ak-hg-app shadow ──
    name: str | None = None

    # ── machineInformation shadow ──
    manufacturer: str | None = None
    model: str | None = None
    firmware: str | None = None
    firmware_code: str | None = None
    hw_serial: str | None = None

    # ── telemetry shadow ──
    battery_level: int | None = None  # "quantity"
    hypa_life: int | None = None  # HEPA filter %
    main_brush_life: int | None = None
    side_brush_life: int | None = None
    mop_life: int | None = None
    wifi_rssi: str | None = None
    wifi_ip: str | None = None
    cleaning_time: int | None = None  # seconds
    cleaning_area: int | None = None  # m²

    # ── state shadow ──
    status: int | None = None  # 0=sleep,1=standBy,2=pause,3=recharging,4=charging,5=sweeping,6=sweepMop,7=mopping,8=upgrading,9=cleaning,10=airDrying,11=dustCollecting,12=buildingMap,13=cuttingHair
    work_mode: int | None = None  # 0=idle,1=auto,5=backCharge,25=border,45=explore,...
    fault: int | None = None  # 0=no fault
    wind: int | None = None  # suction level
    water: int | None = None  # mop water level
    mode: int | None = None
    charge_state: int | None = None
    tank_state: int | None = None
    cloth_state: int | None = None
    volume: int | None = None

    # ── maps shadow ──
    active_map_id: int | None = None
    map_name: str | None = None

    # Raw shadow data for extra_state_attributes
    raw_shadows: dict[str, dict[str, Any]] = field(default_factory=dict)


class KarcherCoordinator(DataUpdateCoordinator[dict[str, KarcherDevice]]):
    """Polls Kärcher cloud for the user's devices and their shadow state."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth: KarcherAuth,
        api: KarcherAPI,
        iot: KarcherIoT,
        user_id: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._auth = auth
        self.api = api
        self.iot = iot
        self.user_id = user_id

    async def _async_update_data(self) -> dict[str, KarcherDevice]:
        try:
            things = await self.api.list_things_dm(self.user_id)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"list_things failed: {err}") from err

        devices: dict[str, KarcherDevice] = {}
        for t in things:
            dm_id = t["id"]
            dev = KarcherDevice(
                dm_id=dm_id,
                device_id=t.get("deviceId", ""),
                part_number=t.get("partNumber", ""),
                serial_number=t.get("serialNumber", ""),
                vendor_id=t.get("vendorId", ""),
                product_id=t.get("productId", ""),
                user_id=t.get("userId", self.user_id),
                is_online=bool(t.get("isOnline")),
                is_provisioned=bool(t.get("isProvisioned")),
            )

            try:
                shadows = await self.iot.get_all_shadows(dm_id)
                dev.raw_shadows = shadows
                self._apply_shadows(dev, shadows)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Shadow read for %s failed: %s", dm_id, err)

            devices[dm_id] = dev
        return devices

    @staticmethod
    def _apply_shadows(dev: KarcherDevice, shadows: dict[str, dict[str, Any]]) -> None:
        # ak-hg-app
        app = shadows.get("ak-hg-app", {})
        dev.name = app.get("name") or dev.name

        # machineInformation
        mi = shadows.get("machineInformation", {})
        dev.manufacturer = mi.get("manufacturer")
        dev.model = mi.get("model")
        dev.firmware = mi.get("firmware")
        dev.firmware_code = mi.get("firmware_code")
        dev.hw_serial = mi.get("serial_number")

        # telemetry
        tel = shadows.get("telemetry", {})
        dev.battery_level = tel.get("quantity")
        dev.hypa_life = tel.get("hypa")
        dev.main_brush_life = tel.get("main_brush")
        dev.side_brush_life = tel.get("side_brush")
        dev.mop_life = tel.get("mop_life")
        net = tel.get("net_status") or {}
        dev.wifi_rssi = net.get("rssi")
        dev.wifi_ip = net.get("ip")
        dev.cleaning_time = tel.get("cleaning_time")
        dev.cleaning_area = tel.get("cleaning_area")

        # state
        st = shadows.get("state", {})
        dev.status = st.get("status")
        dev.fault = st.get("fault")
        dev.wind = st.get("wind")
        dev.water = st.get("water")
        dev.mode = st.get("mode")
        dev.work_mode = st.get("work_mode")
        dev.charge_state = st.get("charge_state")
        dev.tank_state = st.get("tank_state")
        dev.cloth_state = st.get("cloth_state")
        dev.volume = st.get("volume")

        # maps
        maps = shadows.get("maps", {})
        dev.active_map_id = maps.get("activeMapId")
        map_list = maps.get("list") or []
        if map_list:
            dev.map_name = map_list[0].get("name")

"""Camera entity: renders robot vacuum map from protobuf data."""
from __future__ import annotations

import io
import logging
import zlib
from datetime import timedelta
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KarcherCoordinator, KarcherDevice
from .entity import KarcherEntity

_LOGGER = logging.getLogger(__name__)

# Room colours — 10 distinct hues for room IDs 10–59
ROOM_COLORS: list[tuple[int, int, int]] = [
    (129, 199, 212),  # teal
    (180, 210, 140),  # lime green
    (245, 195, 120),  # warm orange
    (210, 160, 210),  # lavender
    (250, 220, 150),  # soft yellow
    (160, 195, 230),  # sky blue
    (230, 170, 160),  # salmon
    (190, 220, 190),  # mint
    (220, 190, 230),  # lilac
    (200, 220, 170),  # pistachio
]

WALL_COLOR = (60, 60, 80)
OBSTACLE_COLOR = (100, 100, 120)
BG_COLOR = (240, 240, 240)
DISCOVERED_COLOR = (220, 220, 220)
CHARGER_COLOR = (0, 180, 60)
ROBOT_COLOR = (30, 120, 230)

ROBOT_PART_NUMBERS = {"1.269-640.0"}

# Don't re-fetch map more often than every 30s (separate from coordinator poll)
MAP_FETCH_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: KarcherCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[KarcherMapCamera] = []
    for dm_id, dev in (coordinator.data or {}).items():
        if dev.part_number in ROBOT_PART_NUMBERS:
            entities.append(KarcherMapCamera(coordinator, dm_id))
    async_add_entities(entities)


class KarcherMapCamera(KarcherEntity, Camera):
    """Camera that renders the robot vacuum map as a PNG image."""

    _attr_translation_key = "map"
    _attr_frame_rate = 0  # static image, not a stream

    def __init__(self, coordinator: KarcherCoordinator, dm_id: str) -> None:
        KarcherEntity.__init__(self, coordinator, dm_id)
        Camera.__init__(self)
        self._attr_unique_id = f"{dm_id}_map"
        self._last_image: bytes | None = None
        self._last_map_id: int | None = None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return map image as PNG bytes."""
        dev = self.device
        if dev is None or dev.active_map_id is None:
            return self._last_image

        # Only re-fetch if map ID changed or we have no image yet
        if self._last_image is not None and dev.active_map_id == self._last_map_id:
            return self._last_image

        try:
            raw = await self.coordinator.api.get_map_data(dev.dm_id, dev.active_map_id)
            png = await self.hass.async_add_executor_job(self._render_map, raw)
            self._last_image = png
            self._last_map_id = dev.active_map_id
        except Exception:
            _LOGGER.exception("Map render failed for %s", dev.dm_id)

        return self._last_image

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dev = self.device
        if dev is None:
            return {}
        attrs: dict[str, Any] = {}
        if dev.map_name:
            attrs["map_name"] = dev.map_name
        if dev.active_map_id is not None:
            attrs["map_id"] = dev.active_map_id

        # Room list from last render
        shadows = dev.raw_shadows.get("maps", {})
        map_list = shadows.get("list") or []
        if map_list:
            attrs["map_count"] = len(map_list)
        return attrs

    def _render_map(self, raw_data: bytes) -> bytes:
        """Decompress zlib, parse protobuf, render PNG. Runs in executor."""
        # Import heavy deps only in executor thread
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            from PIL import Image, ImageDraw
            ImageFont = None  # type: ignore[assignment]
        import numpy as np

        from . import robot_map_pb2

        # Decompress
        if raw_data[:2] == b'\x78\x9c' or raw_data[:2] == b'\x78\x01' or raw_data[:2] == b'\x78\xda':
            data = zlib.decompress(raw_data)
        else:
            data = raw_data

        # Parse protobuf
        robot_map = robot_map_pb2.RobotMap()
        robot_map.ParseFromString(data)

        head = robot_map.mapHead
        size_x = head.sizeX
        size_y = head.sizeY
        resolution = head.resolution
        min_x = head.minX
        min_y = head.minY

        # Build pixel array
        raw_pixels = robot_map.mapData.mapData
        pixels = np.frombuffer(raw_pixels, dtype=np.uint8).reshape((size_y, size_x))

        # Create RGB image
        img_array = np.full((size_y, size_x, 3), BG_COLOR, dtype=np.uint8)

        # Discovered
        img_array[pixels == 1] = DISCOVERED_COLOR

        # Rooms (10-59 = base room, 60-109 = room + covered)
        for val in range(10, 110):
            mask = pixels == val
            if not mask.any():
                continue
            room_id = val if val < 60 else val - 50
            color_idx = (room_id - 10) % len(ROOM_COLORS)
            color = ROOM_COLORS[color_idx]
            # Slightly darken covered rooms
            if val >= 60:
                color = tuple(max(0, c - 20) for c in color)  # type: ignore[assignment]
            img_array[mask] = color

        # Walls (255) and obstacles (191, 193, 195, 196)
        img_array[pixels == 255] = WALL_COLOR
        for obs in (191, 193, 195, 196):
            img_array[pixels == obs] = OBSTACLE_COLOR

        # Flip Y axis (map origin bottom-left, image origin top-left)
        img_array = np.flipud(img_array)

        img = Image.fromarray(img_array)

        # Helper: world coords → pixel coords (flipped Y)
        def world_to_px(wx: float, wy: float) -> tuple[int, int]:
            px = int((wx - min_x) / resolution)
            py = size_y - 1 - int((wy - min_y) / resolution)
            return (px, py)

        draw = ImageDraw.Draw(img)

        # Draw charger
        if robot_map.HasField("chargeStation"):
            cs = robot_map.chargeStation
            cx, cy = world_to_px(cs.x, cs.y)
            r = 6
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CHARGER_COLOR)
            # Cross marker
            draw.line([cx - r, cy, cx + r, cy], fill=(255, 255, 255), width=2)
            draw.line([cx, cy - r, cx, cy + r], fill=(255, 255, 255), width=2)

        # Draw robot position
        if robot_map.HasField("currentPose"):
            rp = robot_map.currentPose
            rx, ry = world_to_px(rp.x, rp.y)
            r = 8
            draw.ellipse([rx - r, ry - r, rx + r, ry + r], fill=ROBOT_COLOR)
            # Direction indicator
            import math
            phi = rp.phi
            dx = int(r * math.cos(phi))
            dy = int(-r * math.sin(phi))  # flip Y
            draw.line([rx, ry, rx + dx, ry + dy], fill=(255, 255, 255), width=2)

        # Draw room labels
        rooms = list(robot_map.roomDataInfo)
        for room in rooms:
            lx, ly = world_to_px(room.roomNamePost.x, room.roomNamePost.y)
            label = room.roomName
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            except Exception:
                font = ImageDraw.ImageDraw.font  # type: ignore[attr-defined]
                font = None
            if font:
                bbox = draw.textbbox((lx, ly), label, font=font, anchor="mm")
                draw.rectangle(bbox, fill=(255, 255, 255, 200))
                draw.text((lx, ly), label, fill=(40, 40, 40), font=font, anchor="mm")
            else:
                draw.text((lx, ly), label, fill=(40, 40, 40))

        # Draw virtual walls / no-go zones
        for wall in robot_map.virtualWalls:
            pts = [(world_to_px(p.x, p.y)) for p in wall.points]
            if len(pts) >= 2:
                if wall.type == 0:  # line wall
                    draw.line(pts, fill=(255, 50, 50), width=2)
                elif len(pts) >= 3:  # polygon zone
                    draw.polygon(pts, outline=(255, 50, 50), fill=None)

        # Crop to content (remove background border)
        bbox = self._find_content_bbox(pixels, size_x, size_y)
        if bbox:
            margin = 10
            x1 = max(0, bbox[0] - margin)
            y1 = max(0, (size_y - 1 - bbox[3]) - margin)  # flip Y
            x2 = min(size_x, bbox[2] + margin)
            y2 = min(size_y, (size_y - 1 - bbox[1]) + margin)  # flip Y
            img = img.crop((x1, y1, x2, y2))

        # Scale up 3x for readability
        new_w = img.width * 3
        new_h = img.height * 3
        img = img.resize((new_w, new_h), Image.NEAREST)

        # Encode as PNG
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    @staticmethod
    def _find_content_bbox(
        pixels: Any, size_x: int, size_y: int
    ) -> tuple[int, int, int, int] | None:
        """Find bounding box of non-background pixels. Returns (minX, minY, maxX, maxY) in pixel coords."""
        import numpy as np

        non_bg = pixels != 0
        if not non_bg.any():
            return None
        rows = np.any(non_bg, axis=1)
        cols = np.any(non_bg, axis=0)
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]
        return (int(x_min), int(y_min), int(x_max), int(y_max))

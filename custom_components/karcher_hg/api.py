"""Kärcher REST API client (api.iot.kaercher.com)."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .auth import KarcherAuth
from .const import API_BASE, API_KEY, API_VERSION, APP_PLATFORM, APP_VERSION, DEFAULT_VENDOR_PRODUCT

_LOGGER = logging.getLogger(__name__)


class KarcherAPI:
    """REST calls against api.iot.kaercher.com using Bearer JWT + x-api-key."""

    def __init__(self, session: aiohttp.ClientSession, auth: KarcherAuth) -> None:
        self._session = session
        self._auth = auth

    async def _headers(self) -> dict[str, str]:
        token = await self._auth.get_id_token()
        return {
            "authorization": f"Bearer {token}",
            "x-api-key": API_KEY,
            "x-api-version": API_VERSION,
            "x-app-version": APP_VERSION,
            "x-app-type": APP_PLATFORM,
            "accept-encoding": "identity",
            "content-type": "application/json",
        }

    async def _get(self, path: str, **params: Any) -> Any:
        headers = await self._headers()
        url = f"{API_BASE}{path}"
        async with self._session.get(url, headers=headers, params=params or None) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"GET {path} {resp.status}: {text[:200]}")
            return await resp.json() if text else None

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        headers = await self._headers()
        url = f"{API_BASE}{path}"
        async with self._session.post(url, headers=headers, json=body or {}) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"POST {path} {resp.status}: {text[:200]}")
            return await resp.json() if text else None

    async def _put(self, path: str, body: dict[str, Any]) -> Any:
        headers = await self._headers()
        url = f"{API_BASE}{path}"
        async with self._session.put(url, headers=headers, json=body) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"PUT {path} {resp.status}: {text[:200]}")
            return await resp.json() if text else None

    async def get_profile(self, country: str = "DE") -> dict[str, Any]:
        return await self._get("/uapi/profile", country=country)

    async def list_things_dm(self, user_id: str) -> list[dict[str, Any]]:
        """Device Management things (returns dmId, deviceId, partNumber, isOnline, ...)."""
        return await self._get("/dmapi/things", userId=user_id)

    async def get_thing_dm(self, dm_id: str) -> dict[str, Any]:
        return await self._get(f"/dmapi/things/{dm_id}")

    async def list_things_aws(self) -> list[dict[str, Any]]:
        """AWS Thing registry (thingId, deviceType, bridgeId, stateData)."""
        return await self._get("/tapi/things")

    async def get_support_status(self) -> dict[str, Any]:
        return await self._get(
            "/aapi/support-status",
            os=APP_PLATFORM,
            appVersion=APP_VERSION,
            flavor="com.kaercher.consumer.devicesapp",
        )

    async def register_local(self, jwt: str) -> dict[str, Any]:
        """Returns {region, thingId, mqttEndpoint, cognitoPoolId}."""
        body = {"jwt": jwt}
        return await self._put("/dapi/registerLocal", body)

    # ── Commands ──────────────────────────────────────────────────────

    async def send_command(
        self,
        dm_id: str,
        command: str,
        payload: dict[str, Any] | None = None,
        vendor_product: str = DEFAULT_VENDOR_PRODUCT,
    ) -> dict[str, Any]:
        """POST /dmapi/things/<dmId>/commands/<vendor>-<product>-<command>.

        Captured and verified against real device. Returns {commandId, ...}.
        """
        path = f"/dmapi/things/{dm_id}/commands/{vendor_product}-{command}"
        return await self._post(path, payload)

    # ── Map data ──────────────────────────────────────────────────────

    async def get_map_data(self, dm_id: str, map_id: str | int) -> bytes:
        """Fetch map binary: GET /dmapi/things/<dmId>/maps/<mapId> → 302 → S3.

        Returns zlib-compressed protobuf bytes (RobotMap).
        """
        headers = await self._headers()
        url = f"{API_BASE}/dmapi/things/{dm_id}/maps/{map_id}"
        async with self._session.get(
            url, headers=headers, allow_redirects=True
        ) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"GET map {dm_id}/{map_id} {resp.status}")
            return await resp.read()

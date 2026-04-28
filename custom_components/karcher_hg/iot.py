"""AWS IoT Data plane: signed Shadow GET/UPDATE via SigV4."""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from .auth import KarcherAuth
from .const import ALL_SHADOW_NAMES, AWS_REGION, IOT_DATA_ENDPOINT, IOT_DATA_HOST

_LOGGER = logging.getLogger(__name__)


def _sigv4_sign(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes,
    creds,  # AwsCreds
    region: str,
    service: str,
) -> dict[str, str]:
    """Build SigV4-signed headers using botocore's signer (sync, fast)."""
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    from botocore.credentials import Credentials

    aws = Credentials(
        access_key=creds.access_key_id,
        secret_key=creds.secret_key,
        token=creds.session_token,
    )
    req = AWSRequest(method=method, url=url, data=body, headers=headers)
    SigV4Auth(aws, service, region).add_auth(req)
    return dict(req.headers.items())


class KarcherIoT:
    """Reads thing shadows over HTTPS Data plane (SigV4-signed)."""

    def __init__(self, session: aiohttp.ClientSession, auth: KarcherAuth) -> None:
        self._session = session
        self._auth = auth

    async def _signed_request(
        self, method: str, path: str, body: bytes = b"", params: dict[str, str] | None = None
    ) -> aiohttp.ClientResponse:
        creds = await self._auth.get_aws_creds()
        from urllib.parse import urlencode

        url = f"{IOT_DATA_ENDPOINT}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        headers = {
            "host": IOT_DATA_HOST,
            "content-type": "application/json",
        }
        signed_headers = _sigv4_sign(method, url, headers, body, creds, AWS_REGION, "iotdata")
        return await self._session.request(method, url, headers=signed_headers, data=body)

    async def get_shadow(
        self, thing_name: str, shadow_name: str
    ) -> dict[str, Any]:
        """Fetch a single named shadow."""
        params = {"name": shadow_name}
        path = f"/things/{thing_name}/shadow"
        async with await self._signed_request("GET", path, params=params) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"GetShadow {thing_name}/{shadow_name} {resp.status}: {text[:200]}")
            return json.loads(text)

    async def get_all_shadows(
        self, thing_name: str, shadow_names: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Fetch all named shadows. Returns {shadow_name: reported_dict}."""
        names = shadow_names or ALL_SHADOW_NAMES
        result: dict[str, dict[str, Any]] = {}
        for name in names:
            try:
                sh = await self.get_shadow(thing_name, name)
                reported = (sh.get("state") or {}).get("reported") or {}
                result[name] = reported
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Shadow %s/%s unavailable", thing_name, name)
                result[name] = {}
        return result

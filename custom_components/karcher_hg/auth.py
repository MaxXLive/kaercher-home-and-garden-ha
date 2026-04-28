"""Auth chain: Cognito IdP refresh + Cognito Identity AWS creds."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp

from .const import (
    AWS_REGION,
    COGNITO_CLIENT_ID,
    COGNITO_IDENTITY_POOL_ID,
    COGNITO_USER_POOL_ID,
)

_LOGGER = logging.getLogger(__name__)

COGNITO_IDP_URL = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/"
COGNITO_IDENTITY_URL = f"https://cognito-identity.{AWS_REGION}.amazonaws.com/"
LOGIN_KEY = f"cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"


@dataclass
class AwsCreds:
    access_key_id: str
    secret_key: str
    session_token: str
    expiration: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.expiration - 60


@dataclass
class CognitoTokens:
    id_token: str
    access_token: str
    refresh_token: str
    expires_at: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at - 60


class KarcherAuth:
    """Owns refresh token, refreshes Cognito tokens + AWS creds."""

    def __init__(self, session: aiohttp.ClientSession, refresh_token: str) -> None:
        self._session = session
        self._tokens: Optional[CognitoTokens] = None
        self._aws: Optional[AwsCreds] = None
        self._identity_id: Optional[str] = None
        self._initial_refresh_token = refresh_token

    async def _refresh_idp_tokens(self) -> CognitoTokens:
        """Exchange refresh_token for fresh id+access tokens via Cognito IdP."""
        rt = self._tokens.refresh_token if self._tokens else self._initial_refresh_token
        body = {
            "ClientId": COGNITO_CLIENT_ID,
            "RefreshToken": rt,
        }
        headers = {
            "x-amz-target": "AWSCognitoIdentityProviderService.GetTokensFromRefreshToken",
            "content-type": "application/x-amz-json-1.1",
        }
        async with self._session.post(COGNITO_IDP_URL, json=body, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                raise RuntimeError(f"Cognito IdP refresh failed: {resp.status} {data}")
        auth = data.get("AuthenticationResult") or {}
        id_token = auth["IdToken"]
        access_token = auth["AccessToken"]
        # Cognito IdP refresh does not always return new refresh_token; keep old
        new_refresh = auth.get("RefreshToken") or rt
        expires_in = auth.get("ExpiresIn", 3600)
        self._tokens = CognitoTokens(
            id_token=id_token,
            access_token=access_token,
            refresh_token=new_refresh,
            expires_at=time.time() + expires_in,
        )
        return self._tokens

    async def get_id_token(self) -> str:
        if self._tokens is None or self._tokens.expired:
            await self._refresh_idp_tokens()
        return self._tokens.id_token  # type: ignore[union-attr]

    async def get_refresh_token(self) -> str:
        if self._tokens is None:
            await self._refresh_idp_tokens()
        return self._tokens.refresh_token  # type: ignore[union-attr]

    async def _get_identity_id(self, id_token: str) -> str:
        if self._identity_id:
            return self._identity_id
        body = {
            "IdentityPoolId": COGNITO_IDENTITY_POOL_ID,
            "Logins": {LOGIN_KEY: id_token},
        }
        headers = {
            "x-amz-target": "AWSCognitoIdentityService.GetId",
            "content-type": "application/x-amz-json-1.1",
        }
        async with self._session.post(COGNITO_IDENTITY_URL, json=body, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                raise RuntimeError(f"Cognito GetId failed: {resp.status} {data}")
        self._identity_id = data["IdentityId"]
        return self._identity_id

    async def get_aws_creds(self) -> AwsCreds:
        """Return fresh AWS Cognito Identity credentials, refreshing if needed."""
        if self._aws and not self._aws.expired:
            return self._aws
        id_token = await self.get_id_token()
        identity_id = await self._get_identity_id(id_token)
        body = {
            "IdentityId": identity_id,
            "Logins": {LOGIN_KEY: id_token},
        }
        headers = {
            "x-amz-target": "AWSCognitoIdentityService.GetCredentialsForIdentity",
            "content-type": "application/x-amz-json-1.1",
        }
        async with self._session.post(COGNITO_IDENTITY_URL, json=body, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                raise RuntimeError(f"GetCredentialsForIdentity failed: {resp.status} {data}")
        creds = data["Credentials"]
        self._aws = AwsCreds(
            access_key_id=creds["AccessKeyId"],
            secret_key=creds["SecretKey"],
            session_token=creds["SessionToken"],
            expiration=float(creds["Expiration"]),
        )
        return self._aws

    @property
    def identity_id(self) -> Optional[str]:
        return self._identity_id

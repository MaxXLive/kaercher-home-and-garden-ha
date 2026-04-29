"""Minimal AWS Cognito USER_SRP_AUTH over aiohttp.

No extra dependencies — uses only hashlib/hmac/os from stdlib + aiohttp.
Based on the well-known Cognito SRP protocol (warrant/pycognito).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import time
from typing import Any

import aiohttp

# fmt: off
# 3072-bit SRP N value used by AWS Cognito
_N_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64"
    "ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7"
    "ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6B"
    "F12FFA06D98A0864D87602733EC86A64521F2B18177B200C"
    "BBE117577A615D6C770988C0BAD946E208E24FA074E5AB31"
    "43DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF"
)
# fmt: on
_G_HEX = "2"
_INFO_BITS = bytearray("Caldera Derived Key", "utf-8")

IDP_URL = "https://cognito-idp.{region}.amazonaws.com/"


# ── helpers ──────────────────────────────────────────────────────────

def _hex_to_long(h: str) -> int:
    return int(h, 16)


def _long_to_hex(n: int) -> str:
    return "%x" % n


def _hash_sha256(buf: bytes | bytearray) -> str:
    h = hashlib.sha256(buf).hexdigest()
    return ("0" * (64 - len(h))) + h


def _hex_hash(hex_str: str) -> str:
    return _hash_sha256(bytearray.fromhex(hex_str))


def _pad_hex(value: int | str) -> str:
    h = _long_to_hex(value) if isinstance(value, int) else value
    if len(h) % 2 == 1:
        h = "0" + h
    elif h[0] in "89abcdef":
        h = "00" + h
    return h


def _compute_hkdf(ikm: bytes, salt: bytes) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    info = _INFO_BITS + bytearray(chr(1), "utf-8")
    return hmac.new(prk, info, hashlib.sha256).digest()[:16]


def _now_str() -> str:
    """Cognito requires: 'Mon Jan 2 15:04:05 UTC 2006' style."""
    return time.strftime("%a %b %-d %H:%M:%S UTC %Y", time.gmtime())


# ── SRP core ─────────────────────────────────────────────────────────

_BIG_N = _hex_to_long(_N_HEX)
_G = _hex_to_long(_G_HEX)
_K = _hex_to_long(_hex_hash("00" + _N_HEX + "0" + _G_HEX))


def _generate_srp_a() -> tuple[int, int]:
    """Return (small_a, big_A)."""
    small_a = _hex_to_long(binascii.hexlify(os.urandom(128)).decode())
    big_a = pow(_G, small_a, _BIG_N)
    if big_a % _BIG_N == 0:
        raise ValueError("SRP safety check: A mod N == 0")
    return small_a, big_a


def _compute_password_claim(
    pool_name: str,
    username: str,
    password: str,
    srp_b: int,
    salt: int,
    small_a: int,
    big_a: int,
    secret_block_b64: str,
    timestamp: str,
) -> str:
    """Compute PASSWORD_CLAIM_SIGNATURE for RespondToAuthChallenge."""
    u_val = _hex_to_long(
        _hex_hash(_pad_hex(big_a) + _pad_hex(srp_b))
    )
    if u_val == 0:
        raise ValueError("SRP safety check: u == 0")

    # x = H(salt | H(poolName | username | ":" | password))
    user_pass_hash = _hash_sha256(
        (pool_name + username + ":" + password).encode("utf-8")
    )
    x_val = _hex_to_long(_hex_hash(_pad_hex(salt) + user_pass_hash))

    # S = (B - k * g^x)^(a + u*x) mod N
    g_mod_pow_xn = pow(_G, x_val, _BIG_N)
    int_val2 = srp_b - _K * g_mod_pow_xn
    s_val = pow(int_val2, small_a + u_val * x_val, _BIG_N)

    hkdf = _compute_hkdf(
        bytearray.fromhex(_pad_hex(s_val)),
        bytearray.fromhex(_pad_hex(_long_to_hex(u_val))),
    )

    secret_block = base64.standard_b64decode(secret_block_b64)
    msg = (
        bytearray(pool_name, "utf-8")
        + bytearray(username, "utf-8")
        + bytearray(secret_block)
        + bytearray(timestamp, "utf-8")
    )
    sig = hmac.new(hkdf, msg, hashlib.sha256).digest()
    return base64.standard_b64encode(sig).decode("utf-8")


# ── public API ───────────────────────────────────────────────────────

async def srp_authenticate(
    session: aiohttp.ClientSession,
    username: str,
    password: str,
    pool_id: str,
    client_id: str,
    region: str = "eu-west-1",
) -> dict[str, Any]:
    """Perform full SRP auth. Returns AuthenticationResult with tokens."""
    url = IDP_URL.format(region=region)
    pool_name = pool_id.split("_")[1]

    small_a, big_a = _generate_srp_a()

    # Step 1: InitiateAuth
    init_body = {
        "AuthFlow": "USER_SRP_AUTH",
        "ClientId": client_id,
        "AuthParameters": {
            "USERNAME": username,
            "SRP_A": _long_to_hex(big_a),
        },
    }
    headers = {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    }
    async with session.post(url, json=init_body, headers=headers) as resp:
        data = await resp.json(content_type=None)
        if resp.status != 200:
            err = data.get("message", data)
            etype = data.get("__type", "")
            if "UserNotFoundException" in etype or "NotAuthorizedException" in etype:
                raise ValueError(f"Login failed: {err}")
            raise RuntimeError(f"Cognito InitiateAuth failed: {resp.status} {err}")

    if data.get("ChallengeName") != "PASSWORD_VERIFIER":
        raise RuntimeError(
            f"Unexpected challenge: {data.get('ChallengeName')} "
            f"(MFA or custom auth not supported yet)"
        )

    cp = data["ChallengeParameters"]
    timestamp = _now_str()

    signature = _compute_password_claim(
        pool_name=pool_name,
        username=cp["USERNAME"],  # server may return canonical username
        password=password,
        srp_b=_hex_to_long(cp["SRP_B"]),
        salt=_hex_to_long(cp["SALT"]),
        small_a=small_a,
        big_a=big_a,
        secret_block_b64=cp["SECRET_BLOCK"],
        timestamp=timestamp,
    )

    # Step 2: RespondToAuthChallenge
    challenge_body = {
        "ChallengeName": "PASSWORD_VERIFIER",
        "ClientId": client_id,
        "ChallengeResponses": {
            "USERNAME": cp["USERNAME"],
            "PASSWORD_CLAIM_SECRET_BLOCK": cp["SECRET_BLOCK"],
            "PASSWORD_CLAIM_SIGNATURE": signature,
            "TIMESTAMP": timestamp,
        },
    }
    if data.get("Session"):
        challenge_body["Session"] = data["Session"]

    headers["X-Amz-Target"] = (
        "AWSCognitoIdentityProviderService.RespondToAuthChallenge"
    )
    async with session.post(url, json=challenge_body, headers=headers) as resp:
        result = await resp.json(content_type=None)
        if resp.status != 200:
            err = result.get("message", result)
            raise RuntimeError(f"Cognito challenge failed: {resp.status} {err}")

    if "AuthenticationResult" not in result:
        raise RuntimeError(
            f"Unexpected response after challenge: {result.get('ChallengeName', 'no tokens')}"
        )

    return result["AuthenticationResult"]

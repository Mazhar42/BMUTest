"""Password hashing (argon2), JWTs, TOTP, app-level encryption (Fernet) and token helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator
from sqlalchemy.engine import Dialect

from app.config import get_settings
from app.core import clock

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def sha256_hex(value: str | bytes) -> str:
    data = value.encode() if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def hmac_hex(value: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def random_token(nbytes: int = 16) -> str:
    """URL-safe random token (16 bytes = 128 bits)."""
    return secrets.token_urlsafe(nbytes)


def random_digits(n: int) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(n))


# ---- JWT -------------------------------------------------------------------------------------------


def encode_jwt(claims: dict[str, Any], ttl: timedelta) -> str:
    now = clock.now()
    payload = {**claims, "iat": int(now.timestamp()), "exp": int((now + ttl).timestamp()), "jti": uuid.uuid4().hex}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def decode_jwt(token: str) -> dict[str, Any]:
    # Use our injectable clock so frozen-time tests behave.
    data: dict[str, Any] = jwt.decode(
        token, get_settings().jwt_secret, algorithms=["HS256"], options={"verify_exp": False, "verify_iat": False}
    )
    if int(data.get("exp", 0)) < int(clock.now().timestamp()):
        raise jwt.ExpiredSignatureError("expired")
    return data


# ---- TOTP ------------------------------------------------------------------------------------------


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="BMU Lab")


def verify_totp(secret: str, code: str, at: datetime | None = None) -> bool:
    return pyotp.TOTP(secret).verify(code.strip(), for_time=at or clock.now(), valid_window=1)


def totp_now(secret: str) -> str:
    return pyotp.TOTP(secret).at(clock.now())


# ---- Encryption ------------------------------------------------------------------------------------


def _fernet() -> Fernet:
    return Fernet(get_settings().app_encryption_key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:  # pragma: no cover - key rotation problem
        raise ValueError("cannot decrypt value") from exc


class EncryptedString(TypeDecorator[str]):
    """Column type that stores Fernet ciphertext (NID, TOTP secrets — ROADMAP §11)."""

    impl = String(512)
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        return encrypt(value) if value is not None else None

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        return decrypt(value) if value is not None else None

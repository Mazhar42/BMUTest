"""Patient OTP login (ROADMAP §6.4): 6-digit code stored hashed, 5-minute TTL, 5 attempts, 3 sends per
15 minutes per mobile (+ per-IP cap). Access JWT 15 min; refresh token in an httpOnly cookie, rotated on
every use — presenting an already-rotated token revokes the whole token family."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import audit, clock
from app.core.actor import Actor
from app.core.errors import AppError, RateLimited, Unauthorized
from app.core.security import decode_jwt, encode_jwt, hmac_hex, random_digits, random_token, sha256_hex
from app.modules.notifications import service as notifications
from app.modules.patients import service as patients
from app.modules.patients.models import Account, OtpChallenge, PatientRefreshToken


class OtpError(AppError):
    status_code = 401


@dataclass
class OtpSent:
    mobile: str
    expires_in: int
    resend_after: int
    debug_code: str | None


@dataclass
class Tokens:
    access_token: str
    expires_in: int
    refresh_token: str
    account: Account


def _code_hash(mobile: str, code: str) -> str:
    return hmac_hex(f"otp:{mobile}:{code}")


def _debug_codes_allowed() -> bool:
    s = get_settings()
    return s.env != "prod" and s.sms_provider == "mock"


def request_otp(db: Session, raw_mobile: str, ip: str | None, lang: str | None) -> OtpSent:
    s = get_settings()
    mobile = patients.normalize_mobile(raw_mobile)
    now = clock.now()
    window_start = now - timedelta(minutes=s.otp_send_window_minutes)
    sent_to_mobile = db.scalar(
        select(func.count()).where(OtpChallenge.mobile == mobile, OtpChallenge.created_at > window_start)
    )
    if (sent_to_mobile or 0) >= s.otp_send_limit_per_mobile:
        oldest = db.scalar(
            select(func.min(OtpChallenge.created_at)).where(
                OtpChallenge.mobile == mobile, OtpChallenge.created_at > window_start
            )
        )
        wait = (oldest + timedelta(minutes=s.otp_send_window_minutes) - now) if oldest else timedelta(minutes=1)
        raise RateLimited("OTP_RATE_LIMITED", minutes=max(1, -(-int(wait.total_seconds()) // 60)))
    if ip:
        from_ip = db.scalar(
            select(func.count()).where(OtpChallenge.requester_ip == ip, OtpChallenge.created_at > window_start)
        )
        if (from_ip or 0) >= s.otp_send_limit_per_ip:
            raise RateLimited("OTP_RATE_LIMITED", minutes=s.otp_send_window_minutes)

    # Older pending codes stop working once a new one is issued.
    db.execute(
        update(OtpChallenge)
        .where(OtpChallenge.mobile == mobile, OtpChallenge.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    code = random_digits(6)
    db.add(
        OtpChallenge(
            id=uuid.uuid4(),
            mobile=mobile,
            code_hash=_code_hash(mobile, code),
            expires_at=now + timedelta(seconds=s.otp_ttl_seconds),
            requester_ip=ip,
        )
    )
    account = db.scalar(select(Account).where(Account.mobile == mobile))
    sms_lang = account.preferred_language if account else (lang if lang in ("bn", "en") else "bn")
    notifications.send_now(db, mobile, "otp", sms_lang, {"otp": code}, redact=code)
    return OtpSent(
        mobile=mobile,
        expires_in=s.otp_ttl_seconds,
        resend_after=60,
        debug_code=code if _debug_codes_allowed() else None,
    )


def verify_otp(db: Session, raw_mobile: str, code: str, lang: str | None) -> Tokens:
    s = get_settings()
    mobile = patients.normalize_mobile(raw_mobile)
    now = clock.now()
    ch = db.scalar(
        select(OtpChallenge)
        .where(OtpChallenge.mobile == mobile, OtpChallenge.consumed_at.is_(None))
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if ch is None or ch.expires_at <= now:
        raise OtpError("OTP_EXPIRED")
    if ch.attempts >= s.otp_max_attempts:
        raise OtpError("OTP_TOO_MANY_ATTEMPTS")
    if _code_hash(mobile, code.strip()) != ch.code_hash:
        ch.attempts += 1
        if ch.attempts >= s.otp_max_attempts:
            ch.consumed_at = now
            raise OtpError("OTP_TOO_MANY_ATTEMPTS")
        raise OtpError("OTP_INVALID")
    ch.consumed_at = now
    account, created = patients.get_or_create_account(db, mobile, lang)
    account.last_login_at = now
    actor = Actor(type="patient", id=account.id, label=f"account:{str(account.id)[:8]}")
    audit.record(db, actor, "patient.login", entity_type="account", entity_id=account.id, after={"new": created})
    return _issue(db, account, uuid.uuid4())


def _issue(db: Session, account: Account, family_id: uuid.UUID) -> Tokens:
    s = get_settings()
    raw = random_token(32)
    db.add(
        PatientRefreshToken(
            id=uuid.uuid4(),
            account_id=account.id,
            token_hash=sha256_hex(raw),
            family_id=family_id,
            expires_at=clock.now() + timedelta(days=s.patient_refresh_token_days),
        )
    )
    ttl = timedelta(minutes=s.patient_access_token_minutes)
    access = encode_jwt({"typ": "patient", "sub": str(account.id)}, ttl)
    return Tokens(access_token=access, expires_in=int(ttl.total_seconds()), refresh_token=raw, account=account)


def refresh(db: Session, raw: str | None) -> Tokens:
    if not raw:
        raise Unauthorized("REFRESH_MISSING")
    row = db.scalar(
        select(PatientRefreshToken).where(PatientRefreshToken.token_hash == sha256_hex(raw)).with_for_update()
    )
    now = clock.now()
    if row is None:
        raise Unauthorized("REFRESH_INVALID")
    if row.revoked_at is not None or row.rotated_at is not None:
        # Reuse of a rotated token: assume theft, revoke the whole family.
        revoke_family(db, row.family_id)
        audit.record(
            db,
            Actor(type="patient", id=row.account_id),
            "patient.refresh_reuse",
            entity_type="account",
            entity_id=row.account_id,
        )
        raise Unauthorized("REFRESH_REUSED")
    if row.expires_at <= now:
        raise Unauthorized("REFRESH_EXPIRED")
    account = db.get(Account, row.account_id)
    if account is None or account.status != "ACTIVE":
        raise Unauthorized("REFRESH_INVALID")
    row.rotated_at = now
    return _issue(db, account, row.family_id)


def revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(PatientRefreshToken)
        .where(PatientRefreshToken.family_id == family_id, PatientRefreshToken.revoked_at.is_(None))
        .values(revoked_at=clock.now())
    )


def logout(db: Session, raw: str | None) -> None:
    if not raw:
        return
    row = db.scalar(select(PatientRefreshToken).where(PatientRefreshToken.token_hash == sha256_hex(raw)))
    if row is not None:
        revoke_family(db, row.family_id)


def authenticate(db: Session, token: str) -> Account:
    try:
        claims = decode_jwt(token)
    except jwt.PyJWTError as exc:
        raise Unauthorized("SESSION_EXPIRED") from exc
    if claims.get("typ") != "patient":
        raise Unauthorized()
    account = db.get(Account, uuid.UUID(claims["sub"]))
    if account is None or account.status != "ACTIVE":
        raise Unauthorized("SESSION_EXPIRED")
    return account

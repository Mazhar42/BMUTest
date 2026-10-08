"""Staff authentication (password + TOTP), sessions with idle lock, staff & device administration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import audit, clock
from app.core.actor import Actor
from app.core.errors import AppError, Conflict, Forbidden, Invalid, NotFound, Unauthorized
from app.core.security import (
    decode_jwt,
    encode_jwt,
    hash_password,
    new_totp_secret,
    random_token,
    sha256_hex,
    totp_uri,
    verify_password,
    verify_totp,
)
from app.modules.identity import schemas
from app.modules.identity.models import Device, DeviceKind, Staff, StaffRole, StaffSession
from app.modules.identity.permissions import (
    DEPARTMENT_SCOPED,
    PRIVILEGED,
    TOTP_REQUIRED,
    Role,
    permissions_for,
)


class SessionLocked(AppError):
    status_code = 423

    def __init__(self) -> None:
        super().__init__("SESSION_LOCKED", "errors.session_locked")


@dataclass
class StaffContext:
    staff: Staff
    session: StaffSession
    actor: Actor


def staff_roles(staff: Staff) -> set[Role]:
    return {r.role for r in staff.roles}


def department_scope(staff: Staff) -> frozenset[uuid.UUID] | None:
    """None = all departments. Scoped roles with a department restrict worklists."""
    scoped = [r for r in staff.roles if r.role in DEPARTMENT_SCOPED]
    unscoped_other = [r for r in staff.roles if r.role not in DEPARTMENT_SCOPED]
    if any(r.role in {Role.SUPER_ADMIN, Role.LAB_ADMIN} for r in unscoped_other):
        return None
    if scoped and all(r.department_id is not None for r in scoped):
        return frozenset(r.department_id for r in scoped if r.department_id is not None)
    return None


def totp_required(staff: Staff) -> bool:
    return staff.totp_enabled or bool(staff_roles(staff) & TOTP_REQUIRED)


def actor_for(staff: Staff, session: StaffSession | None) -> Actor:
    return Actor(
        type="staff",
        id=staff.id,
        label=staff.username,
        permissions=permissions_for(staff_roles(staff)),
        department_ids=department_scope(staff),
        station=session.station if session else None,
    )


def me(staff: Staff, session: StaffSession) -> schemas.StaffMe:
    return schemas.StaffMe(
        id=staff.id,
        username=staff.username,
        full_name=staff.full_name,
        full_name_bn=staff.full_name_bn,
        designation=staff.designation,
        roles=[schemas.RoleOut.model_validate(r) for r in staff.roles],
        permissions=sorted(permissions_for(staff_roles(staff))),
        station=session.station,
        preferred_language=staff.preferred_language,
        totp_enabled=staff.totp_enabled,
        session_expires_at=session.expires_at,
    )


# ---- login ----------------------------------------------------------------------------------------


def _challenge(staff: Staff, station: str | None) -> str:
    return encode_jwt({"typ": "staff_challenge", "sub": str(staff.id), "station": station}, timedelta(minutes=5))


def _start_session(
    db: Session, staff: Staff, station: str | None, ip: str | None, ua: str | None
) -> tuple[str, StaffSession]:
    s = get_settings()
    now = clock.now()
    session = StaffSession(
        id=uuid.uuid4(),
        staff_id=staff.id,
        station=station,
        expires_at=now + timedelta(hours=s.staff_session_hours),
        last_seen_at=now,
        ip=ip,
        user_agent=(ua or "")[:300] or None,
    )
    db.add(session)
    staff.failed_logins = 0
    staff.locked_until = None
    token = encode_jwt(
        {"typ": "staff", "sub": str(staff.id), "sid": str(session.id)}, timedelta(hours=s.staff_session_hours)
    )
    audit.record(
        db,
        actor_for(staff, session),
        "staff.login",
        entity_type="staff",
        entity_id=staff.id,
        after={"station": station},
    )
    return token, session


def login(db: Session, data: schemas.LoginIn, ip: str | None, ua: str | None) -> schemas.LoginOut:
    s = get_settings()
    staff = db.scalar(select(Staff).where(Staff.username == data.username.strip().lower()).with_for_update())
    anon = Actor(type="public", label=data.username[:60])
    if staff is None or not staff.is_active:
        audit.record(db, anon, "staff.login_failed", reason="unknown_or_inactive")
        raise Unauthorized("INVALID_CREDENTIALS")
    now = clock.now()
    if staff.locked_until and staff.locked_until > now:
        raise AppError("ACCOUNT_LOCKED", params={"until": staff.locked_until.isoformat()}, status_code=423)
    if not verify_password(data.password, staff.password_hash):
        staff.failed_logins += 1
        if staff.failed_logins >= s.staff_max_failed_logins:
            staff.locked_until = now + timedelta(minutes=s.staff_lockout_minutes)
        audit.record(
            db,
            anon,
            "staff.login_failed",
            entity_type="staff",
            entity_id=staff.id,
            after={"failed_logins": staff.failed_logins},
        )
        raise Unauthorized("INVALID_CREDENTIALS")

    if totp_required(staff):
        if not staff.totp_enabled:
            secret = new_totp_secret()
            staff.totp_pending_secret = secret
            return schemas.LoginOut(
                status="TOTP_ENROLL",
                challenge=_challenge(staff, data.station),
                otpauth_uri=totp_uri(secret, staff.username),
                totp_secret=secret,
            )
        return schemas.LoginOut(status="TOTP_REQUIRED", challenge=_challenge(staff, data.station))

    token, session = _start_session(db, staff, data.station, ip, ua)
    return schemas.LoginOut(status="OK", access_token=token, me=me(staff, session))


def login_totp(db: Session, data: schemas.TotpIn, ip: str | None, ua: str | None) -> schemas.LoginOut:
    s = get_settings()
    try:
        claims = decode_jwt(data.challenge)
    except jwt.PyJWTError as exc:
        raise Unauthorized("CHALLENGE_EXPIRED") from exc
    if claims.get("typ") != "staff_challenge":
        raise Unauthorized("CHALLENGE_EXPIRED")
    staff = db.get(Staff, uuid.UUID(claims["sub"]), with_for_update=True)
    if staff is None or not staff.is_active:
        raise Unauthorized("INVALID_CREDENTIALS")
    now = clock.now()
    if staff.locked_until and staff.locked_until > now:
        raise AppError("ACCOUNT_LOCKED", params={"until": staff.locked_until.isoformat()}, status_code=423)

    secret = staff.totp_secret if staff.totp_enabled else staff.totp_pending_secret
    if not secret or not verify_totp(secret, data.code):
        staff.failed_logins += 1
        if staff.failed_logins >= s.staff_max_failed_logins:
            staff.locked_until = now + timedelta(minutes=s.staff_lockout_minutes)
        audit.record(
            db, Actor(type="public", label=staff.username), "staff.totp_failed", entity_type="staff", entity_id=staff.id
        )
        raise Unauthorized("INVALID_TOTP")
    if not staff.totp_enabled:
        staff.totp_secret = secret
        staff.totp_pending_secret = None
        staff.totp_enabled = True
        audit.record(db, actor_for(staff, None), "staff.totp_enrolled", entity_type="staff", entity_id=staff.id)
    token, session = _start_session(db, staff, claims.get("station"), ip, ua)
    return schemas.LoginOut(status="OK", access_token=token, me=me(staff, session))


def authenticate(db: Session, token: str, *, allow_locked: bool = False) -> StaffContext:
    """Validate a staff bearer token: session alive, not expired, not idle-locked."""
    try:
        claims = decode_jwt(token)
    except jwt.PyJWTError as exc:
        raise Unauthorized("SESSION_EXPIRED") from exc
    if claims.get("typ") != "staff":
        raise Unauthorized()
    session = db.get(StaffSession, uuid.UUID(claims["sid"]))
    now = clock.now()
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise Unauthorized("SESSION_EXPIRED")
    staff = db.get(Staff, session.staff_id)
    if staff is None or not staff.is_active:
        raise Unauthorized("SESSION_EXPIRED")
    idle = timedelta(minutes=get_settings().staff_idle_lock_minutes)
    if not allow_locked and now - session.last_seen_at > idle:
        raise SessionLocked()
    if not allow_locked and now - session.last_seen_at > timedelta(seconds=60):
        session.last_seen_at = now
        db.commit()
    return StaffContext(staff=staff, session=session, actor=actor_for(staff, session))


def unlock(db: Session, ctx: StaffContext, secret: str) -> None:
    staff = ctx.staff
    ok = verify_password(secret, staff.password_hash) or (
        staff.pin_hash is not None and verify_password(secret, staff.pin_hash)
    )
    if not ok:
        audit.record(db, ctx.actor, "staff.unlock_failed", entity_type="staff", entity_id=staff.id)
        staff.failed_logins += 1
        if staff.failed_logins >= get_settings().staff_max_failed_logins:
            ctx.session.revoked_at = clock.now()
        raise Unauthorized("INVALID_CREDENTIALS")
    staff.failed_logins = 0
    ctx.session.last_seen_at = clock.now()
    audit.record(db, ctx.actor, "staff.unlock", entity_type="staff", entity_id=staff.id)


def lock(db: Session, ctx: StaffContext) -> None:
    """Lock now: make the session look idle so the next request requires unlock."""
    idle = timedelta(minutes=get_settings().staff_idle_lock_minutes)
    ctx.session.last_seen_at = clock.now() - idle - timedelta(seconds=1)
    audit.record(db, ctx.actor, "staff.lock", entity_type="staff", entity_id=ctx.staff.id)


def logout(db: Session, ctx: StaffContext) -> None:
    ctx.session.revoked_at = clock.now()
    audit.record(db, ctx.actor, "staff.logout", entity_type="staff", entity_id=ctx.staff.id)


def set_pin(db: Session, ctx: StaffContext, data: schemas.PinIn) -> None:
    if not verify_password(data.password, ctx.staff.password_hash):
        raise Unauthorized("INVALID_CREDENTIALS")
    ctx.staff.pin_hash = hash_password(data.pin)
    audit.record(db, ctx.actor, "staff.pin_set", entity_type="staff", entity_id=ctx.staff.id)


def change_password(db: Session, ctx: StaffContext, data: schemas.PasswordChangeIn) -> None:
    if not verify_password(data.current_password, ctx.staff.password_hash):
        raise Unauthorized("INVALID_CREDENTIALS")
    ctx.staff.password_hash = hash_password(data.new_password)
    ctx.staff.must_change_password = False
    audit.record(db, ctx.actor, "staff.password_changed", entity_type="staff", entity_id=ctx.staff.id)


# ---- administration -------------------------------------------------------------------------------


def _check_role_grant(actor: Actor, roles: list[schemas.RoleIn]) -> None:
    if any(r.role in PRIVILEGED for r in roles) and not actor.can("admin.create"):
        raise Forbidden("ONLY_SUPER_ADMIN_GRANTS_ADMIN")


def create_staff(db: Session, data: schemas.StaffCreate, actor: Actor) -> Staff:
    _check_role_grant(actor, data.roles)
    if db.scalar(select(Staff).where(Staff.username == data.username)):
        raise Conflict("USERNAME_TAKEN")
    staff = Staff(
        id=uuid.uuid4(),
        username=data.username,
        full_name=data.full_name,
        full_name_bn=data.full_name_bn,
        designation=data.designation,
        mobile=data.mobile,
        password_hash=hash_password(data.password),
        must_change_password=True,
        roles=[StaffRole(id=uuid.uuid4(), role=r.role, department_id=r.department_id) for r in data.roles],
    )
    db.add(staff)
    audit.record(
        db,
        actor,
        "staff.create",
        entity_type="staff",
        entity_id=staff.id,
        after={"username": staff.username, "roles": [r.role.value for r in data.roles]},
    )
    return staff


def update_staff(db: Session, staff_id: uuid.UUID, data: schemas.StaffUpdate, actor: Actor) -> Staff:
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise NotFound("staff")
    if staff_roles(staff) & PRIVILEGED and not actor.can("admin.create"):
        raise Forbidden("ONLY_SUPER_ADMIN_GRANTS_ADMIN")
    before = {"roles": sorted(r.role.value for r in staff.roles), "is_active": staff.is_active}
    for field in ("full_name", "full_name_bn", "designation", "mobile", "is_active"):
        value = getattr(data, field)
        if value is not None:
            setattr(staff, field, value)
    if data.roles is not None:
        _check_role_grant(actor, data.roles)
        if (
            staff.id == actor.id
            and Role.SUPER_ADMIN in staff_roles(staff)
            and all(r.role != Role.SUPER_ADMIN for r in data.roles)
        ):
            raise Invalid("CANNOT_DEMOTE_SELF")
        staff.roles.clear()
        db.flush()
        staff.roles.extend(StaffRole(id=uuid.uuid4(), role=r.role, department_id=r.department_id) for r in data.roles)
    audit.record(
        db,
        actor,
        "staff.update",
        entity_type="staff",
        entity_id=staff.id,
        before=before,
        after={"roles": sorted(r.role.value for r in staff.roles), "is_active": staff.is_active},
    )
    return staff


def reset_totp(db: Session, staff_id: uuid.UUID, actor: Actor) -> None:
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise NotFound("staff")
    staff.totp_secret = None
    staff.totp_pending_secret = None
    staff.totp_enabled = False
    audit.record(db, actor, "staff.totp_reset", entity_type="staff", entity_id=staff.id)


def reset_password(db: Session, staff_id: uuid.UUID, new_password: str, actor: Actor) -> None:
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise NotFound("staff")
    if staff_roles(staff) & PRIVILEGED and not actor.can("admin.create"):
        raise Forbidden("ONLY_SUPER_ADMIN_GRANTS_ADMIN")
    staff.password_hash = hash_password(new_password)
    staff.must_change_password = True
    staff.failed_logins = 0
    staff.locked_until = None
    audit.record(db, actor, "staff.password_reset", entity_type="staff", entity_id=staff.id)


def create_device(db: Session, data: schemas.DeviceCreate, actor: Actor) -> tuple[Device, str]:
    token = random_token(24)
    device = Device(
        id=uuid.uuid4(),
        name=data.name,
        kind=data.kind,
        queue_id=data.queue_id,
        token_hash=sha256_hex(token),
        created_by=actor.id,
    )
    db.add(device)
    audit.record(
        db,
        actor,
        "device.create",
        entity_type="device",
        entity_id=device.id,
        after={"name": data.name, "kind": data.kind.value},
    )
    return device, token


def authenticate_device(db: Session, token: str, kinds: set[DeviceKind]) -> Device:
    device = db.scalar(select(Device).where(Device.token_hash == sha256_hex(token)))
    if device is None or not device.is_active or device.kind not in kinds:
        raise Unauthorized("DEVICE_UNAUTHORIZED")
    now = clock.now()
    if device.last_seen_at is None or now - device.last_seen_at > timedelta(minutes=1):
        device.last_seen_at = now
        db.commit()
    return device


def create_superadmin(db: Session, username: str, full_name: str, password: str) -> Staff:
    if db.scalar(select(Staff).where(Staff.username == username)):
        raise Conflict("USERNAME_TAKEN")
    staff = Staff(
        id=uuid.uuid4(),
        username=username,
        full_name=full_name,
        password_hash=hash_password(password),
        roles=[StaffRole(id=uuid.uuid4(), role=Role.SUPER_ADMIN)],
    )
    db.add(staff)
    audit.record(
        db,
        Actor(type="system", label="cli"),
        "staff.create_superadmin",
        entity_type="staff",
        entity_id=staff.id,
        after={"username": username},
    )
    return staff


def staff_name(db: Session, staff_id: uuid.UUID | None) -> str | None:
    """Display name for slips and order screens."""
    if staff_id is None:
        return None
    staff = db.get(Staff, staff_id)
    return staff.full_name if staff else None

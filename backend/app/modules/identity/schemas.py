from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.identity.models import DeviceKind
from app.modules.identity.permissions import Role


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)
    station: str | None = Field(default=None, max_length=60)


class TotpIn(BaseModel):
    challenge: str
    code: str = Field(min_length=6, max_length=8)


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    role: Role
    department_id: uuid.UUID | None


class StaffMe(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    full_name_bn: str | None
    designation: str | None
    roles: list[RoleOut]
    permissions: list[str]
    station: str | None
    preferred_language: str
    totp_enabled: bool
    session_expires_at: datetime


class LoginOut(BaseModel):
    status: Literal["OK", "TOTP_REQUIRED", "TOTP_ENROLL"]
    access_token: str | None = None
    challenge: str | None = None
    otpauth_uri: str | None = None
    totp_secret: str | None = None
    me: StaffMe | None = None


class UnlockIn(BaseModel):
    secret: str = Field(min_length=1, max_length=200, description="Password or PIN")


class PreferencesIn(BaseModel):
    preferred_language: Literal["bn", "en"]


class PinIn(BaseModel):
    password: str
    pin: str = Field(pattern=r"^\d{4,6}$")


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


class RoleIn(BaseModel):
    role: Role
    department_id: uuid.UUID | None = None


class StaffCreate(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9_.]{3,60}$")
    full_name: str = Field(min_length=2, max_length=120)
    full_name_bn: str | None = None
    designation: str | None = None
    mobile: str | None = None
    password: str = Field(min_length=10, max_length=200)
    roles: list[RoleIn] = Field(min_length=1)


class StaffUpdate(BaseModel):
    full_name: str | None = None
    full_name_bn: str | None = None
    designation: str | None = None
    mobile: str | None = None
    is_active: bool | None = None
    roles: list[RoleIn] | None = None


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    full_name: str
    full_name_bn: str | None
    designation: str | None
    mobile: str | None
    is_active: bool
    totp_enabled: bool
    locked_until: datetime | None
    roles: list[RoleOut]
    created_at: datetime


class PasswordResetIn(BaseModel):
    new_password: str = Field(min_length=10, max_length=200)


class DeviceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    kind: DeviceKind
    queue_id: str = Field(default="main", max_length=40)


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    kind: DeviceKind
    queue_id: str
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime


class DeviceCreated(DeviceOut):
    token: str


# ---- patient OTP auth ----------------------------------------------------------------------------


class OtpRequestIn(BaseModel):
    mobile: str = Field(min_length=10, max_length=20)
    lang: Literal["bn", "en"] | None = None


class OtpRequestOut(BaseModel):
    mobile: str
    expires_in: int
    resend_after: int
    debug_code: str | None = Field(default=None, description="Dev/test only (mock SMS); never set in prod")


class OtpVerifyIn(BaseModel):
    mobile: str = Field(min_length=10, max_length=20)
    code: str = Field(pattern=r"^\d{6}$")
    lang: Literal["bn", "en"] | None = None


class PatientTokenOut(BaseModel):
    access_token: str
    expires_in: int
    account_id: uuid.UUID

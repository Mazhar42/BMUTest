from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import clock
from app.core.security import EncryptedString
from app.db import Entity, str_enum


class Channel(StrEnum):
    APP = "APP"
    WEB = "WEB"
    HELPDESK = "HELPDESK"
    WALKIN = "WALKIN"
    KIOSK = "KIOSK"
    HOME = "HOME"
    BACKENTRY = "BACKENTRY"


class Sex(StrEnum):
    M = "M"
    F = "F"
    O = "O"  # noqa: E741


class Relation(StrEnum):
    SELF = "SELF"
    SPOUSE = "SPOUSE"
    CHILD = "CHILD"
    PARENT = "PARENT"
    SIBLING = "SIBLING"
    OTHER = "OTHER"


class Account(Entity):
    """A mobile number that logs in with OTP. It may manage several patients (family)."""

    __tablename__ = "account"

    mobile: Mapped[str] = mapped_column(String(16), unique=True)  # E.164
    preferred_language: Mapped[str] = mapped_column(String(2), default="bn")
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    last_login_at: Mapped[datetime | None]

    patients: Mapped[list[Patient]] = relationship(
        back_populates="account", lazy="selectin", order_by="Patient.created_at"
    )


class Patient(Entity):
    __tablename__ = "patient"

    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("account.id"), index=True)
    hospital_patient_no: Mapped[str | None] = mapped_column(String(40), index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    full_name_bn: Mapped[str | None] = mapped_column(String(120))
    sex: Mapped[Sex] = mapped_column(str_enum(Sex, 1))
    date_of_birth: Mapped[date | None]
    age_years: Mapped[int | None]
    age_estimated: Mapped[bool] = mapped_column(default=False)
    mobile: Mapped[str | None] = mapped_column(String(16), index=True)
    nid: Mapped[str | None] = mapped_column(EncryptedString())
    relation_to_account: Mapped[Relation] = mapped_column(str_enum(Relation), default=Relation.SELF)
    created_channel: Mapped[Channel] = mapped_column(str_enum(Channel))
    created_by_staff_id: Mapped[uuid.UUID | None]
    name_search: Mapped[str] = mapped_column(String(260), default="")

    account: Mapped[Account | None] = relationship(back_populates="patients")

    def age_on(self, on: date) -> int | None:
        """Whole years on a date: from the date of birth, else the (estimated) age recorded at registration."""
        if self.date_of_birth is not None:
            dob = self.date_of_birth
            return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))
        if self.age_years is None:
            return None
        recorded = clock.to_local(self.created_at).date() if self.created_at else on
        return self.age_years + max(0, on.year - recorded.year - ((on.month, on.day) < (recorded.month, recorded.day)))

    @property
    def age(self) -> int | None:
        return self.age_on(clock.today())

    @property
    def has_nid(self) -> bool:
        return self.nid is not None

    __table_args__ = (
        Index(
            "ix_patient_name_trgm",
            "name_search",
            postgresql_using="gin",
            postgresql_ops={"name_search": "gin_trgm_ops"},
        ),
    )


class OtpChallenge(Entity):
    __tablename__ = "otp_challenge"

    mobile: Mapped[str] = mapped_column(String(16), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime]
    attempts: Mapped[int] = mapped_column(default=0)
    consumed_at: Mapped[datetime | None]
    requester_ip: Mapped[str | None] = mapped_column(String(64), index=True)


class PatientRefreshToken(Entity):
    """Rotated on every use; reuse of a rotated token revokes the whole family."""

    __tablename__ = "patient_refresh_token"

    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    rotated_at: Mapped[datetime | None]

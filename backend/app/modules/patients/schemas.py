from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.patients.models import Channel, Relation, Sex


class PatientIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    full_name_bn: str | None = Field(default=None, max_length=120)
    sex: Sex
    date_of_birth: date | None = None
    age_years: int | None = Field(default=None, ge=0, le=130)
    relation_to_account: Relation = Relation.SELF
    mobile: str | None = Field(default=None, max_length=20)
    hospital_patient_no: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def _dob_or_age(self) -> Self:
        if (self.date_of_birth is None) == (self.age_years is None):
            raise ValueError("give exactly one of date_of_birth or age_years")
        return self


class StaffPatientIn(PatientIn):
    relation_to_account: Relation = Relation.SELF
    nid: str | None = Field(default=None, max_length=20, pattern=r"^\d{10,17}$")
    force: bool = Field(default=False, description="Register even if possible duplicates were found")


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    full_name_bn: str | None = Field(default=None, max_length=120)
    sex: Sex | None = None
    date_of_birth: date | None = None
    age_years: int | None = Field(default=None, ge=0, le=130)
    mobile: str | None = Field(default=None, max_length=20)
    hospital_patient_no: str | None = Field(default=None, max_length=40)


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    full_name_bn: str | None
    sex: Sex
    date_of_birth: date | None
    age_years: int | None
    age_estimated: bool
    age: int | None = Field(description="Age in whole years today (Dhaka)")
    mobile: str | None
    relation_to_account: Relation
    hospital_patient_no: str | None
    created_channel: Channel
    created_at: datetime


class StaffPatientOut(PatientOut):
    account_id: uuid.UUID | None
    has_nid: bool


class DuplicateCandidate(BaseModel):
    id: uuid.UUID
    full_name: str
    sex: Sex
    age: int | None
    mobile: str | None
    reason: Literal["MOBILE", "NAME"]


class AccountOut(BaseModel):
    id: uuid.UUID
    mobile: str
    preferred_language: str
    patients: list[PatientOut]


class AccountPrefsIn(BaseModel):
    preferred_language: Literal["bn", "en"]

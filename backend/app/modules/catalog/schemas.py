from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.catalog.models import (
    CollectionResource,
    ContainerType,
    FeeCategory,
    ResultMode,
    SpecimenType,
    ValueType,
)


class DepartmentIn(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_]{2,20}$")
    name_en: str = Field(min_length=2, max_length=120)
    name_bn: str = Field(min_length=1, max_length=120)
    result_mode: ResultMode = ResultMode.STRUCTURED
    report_signatory_staff_ids: list[uuid.UUID] = []
    sort: int = 0
    active: bool = True


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name_en: str
    name_bn: str
    result_mode: ResultMode
    report_signatory_staff_ids: list[uuid.UUID]
    sort: int
    active: bool


class DepartmentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name_en: str
    name_bn: str


class TestOut(BaseModel):
    """Public test card (no internal fields)."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name_en: str
    name_bn: str
    abbreviation: str
    aliases: list[str]
    department: DepartmentBrief
    specimen_type: SpecimenType
    container_type: ContainerType
    collection_resource: CollectionResource
    fasting_required: bool
    fasting_hours: int | None
    prep_en: str | None
    prep_bn: str | None
    tat_hours: int
    requires_prescription: bool
    home_collectable: bool
    active: bool
    price: int | None = Field(default=None, description="Current GENERAL price in paisa")


class TestIn(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_\-]{2,30}$")
    name_en: str = Field(min_length=2, max_length=160)
    name_bn: str = Field(min_length=1, max_length=160)
    abbreviation: str = Field(min_length=1, max_length=20)
    aliases: list[str] = []
    department_id: uuid.UUID
    specimen_type: SpecimenType
    container_type: ContainerType
    collection_resource: CollectionResource
    fasting_required: bool = False
    fasting_hours: int | None = None
    prep_en: str | None = None
    prep_bn: str | None = None
    tat_hours: int = Field(default=24, ge=1, le=24 * 60)
    requires_prescription: bool = True
    home_collectable: bool = True
    active: bool = True
    sort: int = 0
    price: int | None = Field(default=None, ge=0, description="Initial GENERAL price (paisa)")


class TestUpdate(BaseModel):
    name_en: str | None = None
    name_bn: str | None = None
    abbreviation: str | None = None
    aliases: list[str] | None = None
    department_id: uuid.UUID | None = None
    specimen_type: SpecimenType | None = None
    container_type: ContainerType | None = None
    collection_resource: CollectionResource | None = None
    fasting_required: bool | None = None
    fasting_hours: int | None = None
    prep_en: str | None = None
    prep_bn: str | None = None
    tat_hours: int | None = None
    requires_prescription: bool | None = None
    home_collectable: bool | None = None
    active: bool | None = None
    sort: int | None = None


class PriceIn(BaseModel):
    amount: int = Field(ge=0, description="paisa")
    fee_category: FeeCategory = FeeCategory.GENERAL


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    amount: int
    fee_category: FeeCategory
    effective_from: datetime
    effective_to: datetime | None


class RangeIO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sex: str | None = Field(default=None, pattern=r"^[MF]$")
    age_min_days: int | None = None
    age_max_days: int | None = None
    low: Decimal | None = None
    high: Decimal | None = None
    text: str | None = None


class ParameterIO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID | None = None
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=120)
    unit: str | None = None
    decimals: int = Field(default=1, ge=0, le=4)
    sort: int = 0
    value_type: ValueType = ValueType.NUMERIC
    options: list[str] = []
    critical_low: Decimal | None = None
    critical_high: Decimal | None = None
    analyzer_code: str | None = None
    ranges: list[RangeIO] = []


class TestDetail(TestOut):
    sort: int
    prices: list[PriceOut]
    parameters: list[ParameterIO]


class ImportResult(BaseModel):
    kind: str
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    price_changes: int = 0
    errors: list[str] = []

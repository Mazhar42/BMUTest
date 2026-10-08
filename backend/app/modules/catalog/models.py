from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Entity, str_enum


class ResultMode(StrEnum):
    STRUCTURED = "STRUCTURED"
    PDF_UPLOAD = "PDF_UPLOAD"


class SpecimenType(StrEnum):
    BLOOD = "BLOOD"
    URINE = "URINE"
    STOOL = "STOOL"
    SWAB = "SWAB"
    OTHER = "OTHER"


class ContainerType(StrEnum):
    EDTA = "EDTA"
    PLAIN = "PLAIN"
    SST = "SST"
    FLUORIDE = "FLUORIDE"
    CITRATE = "CITRATE"
    HEPARIN = "HEPARIN"
    URINE_CUP = "URINE_CUP"
    STOOL_CUP = "STOOL_CUP"
    BLOOD_CULTURE = "BLOOD_CULTURE"
    SWAB_TUBE = "SWAB_TUBE"
    OTHER = "OTHER"


class CollectionResource(StrEnum):
    BLOOD_COLLECTION = "BLOOD_COLLECTION"
    URINE = "URINE"
    SPECIAL = "SPECIAL"


class FeeCategory(StrEnum):
    GENERAL = "GENERAL"
    FREE = "FREE"
    POOR_FUND = "POOR_FUND"
    STAFF = "STAFF"
    CONCESSION = "CONCESSION"


class ValueType(StrEnum):
    NUMERIC = "NUMERIC"
    TEXT = "TEXT"
    OPTION = "OPTION"


class Department(Entity):
    __tablename__ = "department"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name_en: Mapped[str] = mapped_column(String(120))
    name_bn: Mapped[str] = mapped_column(String(120))
    result_mode: Mapped[ResultMode] = mapped_column(str_enum(ResultMode), default=ResultMode.STRUCTURED)
    report_signatory_staff_ids: Mapped[list[Any]] = mapped_column(default=list)
    sort: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)


class LabTest(Entity):
    __tablename__ = "lab_test"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name_en: Mapped[str] = mapped_column(String(160))
    name_bn: Mapped[str] = mapped_column(String(160))
    abbreviation: Mapped[str] = mapped_column(String(20))
    aliases: Mapped[list[Any]] = mapped_column(default=list)
    search_text: Mapped[str] = mapped_column(Text, default="")
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("department.id"), index=True)
    specimen_type: Mapped[SpecimenType] = mapped_column(str_enum(SpecimenType))
    container_type: Mapped[ContainerType] = mapped_column(str_enum(ContainerType))
    collection_resource: Mapped[CollectionResource] = mapped_column(str_enum(CollectionResource, 24))
    fasting_required: Mapped[bool] = mapped_column(default=False)
    fasting_hours: Mapped[int | None]
    prep_en: Mapped[str | None] = mapped_column(Text)
    prep_bn: Mapped[str | None] = mapped_column(Text)
    tat_hours: Mapped[int] = mapped_column(default=24)
    requires_prescription: Mapped[bool] = mapped_column(default=True)
    home_collectable: Mapped[bool] = mapped_column(default=True)
    active: Mapped[bool] = mapped_column(default=True)
    sort: Mapped[int] = mapped_column(default=0)

    department: Mapped[Department] = relationship(lazy="joined")
    prices: Mapped[list[LabTestPrice]] = relationship(
        back_populates="test", order_by="LabTestPrice.effective_from.desc()", lazy="selectin"
    )
    parameters: Mapped[list[TestParameter]] = relationship(
        back_populates="test", order_by="TestParameter.sort", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "ix_lab_test_search_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )


class LabTestPrice(Entity):
    """Price history. An order item snapshots the price at submission."""

    __tablename__ = "lab_test_price"

    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_test.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int]  # paisa
    fee_category: Mapped[FeeCategory] = mapped_column(str_enum(FeeCategory), default=FeeCategory.GENERAL)
    effective_from: Mapped[datetime]
    effective_to: Mapped[datetime | None]
    created_by: Mapped[uuid.UUID | None]

    test: Mapped[LabTest] = relationship(back_populates="prices")


class TestParameter(Entity):
    __tablename__ = "test_parameter"
    __table_args__ = (UniqueConstraint("test_id", "code"),)

    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_test.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str | None] = mapped_column(String(30))
    decimals: Mapped[int] = mapped_column(default=1)
    sort: Mapped[int] = mapped_column(default=0)
    value_type: Mapped[ValueType] = mapped_column(str_enum(ValueType), default=ValueType.NUMERIC)
    options: Mapped[list[Any]] = mapped_column(default=list)
    critical_low: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    critical_high: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    analyzer_code: Mapped[str | None] = mapped_column(String(40), index=True)

    test: Mapped[LabTest] = relationship(back_populates="parameters")
    ranges: Mapped[list[ReferenceRange]] = relationship(
        back_populates="parameter", lazy="selectin", cascade="all, delete-orphan"
    )


class ReferenceRange(Entity):
    __tablename__ = "reference_range"

    parameter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_parameter.id", ondelete="CASCADE"), index=True)
    sex: Mapped[str | None] = mapped_column(String(1))  # M / F / None = any
    age_min_days: Mapped[int | None]
    age_max_days: Mapped[int | None]
    low: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    text: Mapped[str | None] = mapped_column(String(200))

    parameter: Mapped[TestParameter] = relationship(back_populates="ranges")

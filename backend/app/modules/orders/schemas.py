from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.catalog.models import ContainerType, FeeCategory, SpecimenType
from app.modules.orders.models import ItemStatus, OrderPriority, OrderStatus, WaiverStatus
from app.modules.patients.models import Channel, Sex

TestIds = list[uuid.UUID]


class SubmitOrderIn(BaseModel):
    patient_id: uuid.UUID
    prescription_id: uuid.UUID | None = None
    test_ids: TestIds = Field(min_length=1, max_length=30)
    notes: str | None = Field(default=None, max_length=500)
    lang: Literal["bn", "en"] | None = None


class ClarificationResponseIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    test_ids: TestIds | None = Field(default=None, min_length=1, max_length=30)


class VerifyIn(BaseModel):
    test_ids: TestIds | None = Field(default=None, min_length=1, max_length=30, description="Replace the tests")
    note: str | None = Field(default=None, max_length=500)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class WalkinIn(BaseModel):
    patient_id: uuid.UUID
    test_ids: TestIds = Field(min_length=1, max_length=30)
    prescription_id: uuid.UUID | None = None
    priority: OrderPriority = OrderPriority.NORMAL
    fee_category: FeeCategory = FeeCategory.GENERAL
    waiver_reason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=500)
    lang: Literal["bn", "en"] = "bn"

    @model_validator(mode="after")
    def _waiver_reason(self) -> Self:
        if self.fee_category != FeeCategory.GENERAL and not (self.waiver_reason or "").strip():
            raise ValueError("waiver_reason is required for a non-GENERAL fee category")
        return self


class WaiverRequestIn(BaseModel):
    fee_category: FeeCategory
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def _not_general(self) -> Self:
        if self.fee_category == FeeCategory.GENERAL:
            raise ValueError("choose a waiver fee category")
        return self


class WaiverDecisionIn(BaseModel):
    approve: bool
    discount: int | None = Field(default=None, gt=0, description="Approved discount in paisa")
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def _discount(self) -> Self:
        if self.approve and self.discount is None:
            raise ValueError("discount is required when approving")
        return self


# ---- output ----------------------------------------------------------------------------------------


class PatientBrief(BaseModel):
    id: uuid.UUID
    full_name: str
    full_name_bn: str | None
    sex: Sex
    age: int | None
    mobile: str | None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    test_id: uuid.UUID
    department_id: uuid.UUID
    test_code: str
    test_name_en: str
    test_name_bn: str
    abbreviation: str
    price_snapshot: int
    status: ItemStatus
    # live catalog information shown with the item (preparation is never snapshotted into results)
    specimen_type: SpecimenType | None = None
    container_type: ContainerType | None = None
    fasting_required: bool = False
    fasting_hours: int | None = None
    prep_en: str | None = None
    prep_bn: str | None = None
    tat_hours: int | None = None


class TimelineStep(BaseModel):
    key: Literal["submitted", "verified", "paid", "collected", "reported"]
    state: Literal["done", "current", "pending", "error"]
    at: datetime | None = None
    note: str | None = None


class PrescriptionBrief(BaseModel):
    id: uuid.UUID
    image_count: int
    doctor_name: str | None
    status: str


class WaiverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_id: uuid.UUID
    fee_category: FeeCategory
    requested_by: uuid.UUID
    request_reason: str
    status: WaiverStatus
    status_reason: str | None
    decided_by: uuid.UUID | None
    approved_discount: int | None
    created_at: datetime


class PaymentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    method: str
    amount: int
    status: str
    paid_at: datetime | None


class OrderOut(BaseModel):
    """What the patient sees."""

    id: uuid.UUID
    order_code: str | None
    status: OrderStatus
    status_reason: str | None
    channel: Channel
    priority: OrderPriority
    fee_category: FeeCategory
    patient: PatientBrief
    items: list[OrderItemOut]
    subtotal: int
    discount: int
    total: int
    amount_due: int
    notes: str | None
    clarification_note: str | None
    submitted_at: datetime | None
    sla_due_at: datetime | None
    verified_at: datetime | None
    needs_fasting: bool
    max_tat_hours: int | None
    prescription: PrescriptionBrief | None
    timeline: list[TimelineStep]
    created_at: datetime


class StaffOrderOut(OrderOut):
    lang: str
    overdue: bool
    slip_print_count: int
    created_by_staff_id: uuid.UUID | None
    verified_by_staff_id: uuid.UUID | None
    waiver_approved_by: uuid.UUID | None
    waivers: list[WaiverOut]
    payments: list[PaymentBrief]


class OrderRow(BaseModel):
    id: uuid.UUID
    order_code: str | None
    status: OrderStatus
    channel: Channel
    priority: OrderPriority
    fee_category: FeeCategory
    patient_name: str
    patient_sex: Sex
    patient_age: int | None
    tests: list[str]
    total: int
    submitted_at: datetime | None
    sla_due_at: datetime | None
    overdue: bool


class OrderPage(BaseModel):
    items: list[OrderRow]
    next_cursor: str | None


class WaiverQueueRow(BaseModel):
    waiver: WaiverOut
    order: OrderRow
    subtotal: int

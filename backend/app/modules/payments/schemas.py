from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.orders.models import OrderPriority, OrderStatus
from app.modules.payments.models import LineMatch, PaymentMethod, PaymentStatus, RefundMode, RefundStatus
from app.modules.queue.models import QueueName, TokenStatus

TellerState = Literal["RECEIVABLE", "ALREADY_PAID", "NOT_VERIFIED", "EXPIRED", "CLOSED"]


class TokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    label: str
    queue: QueueName
    number: int
    status: TokenStatus


class PaidInfo(BaseModel):
    paid_at: datetime | None
    method: PaymentMethod
    amount: int


class LookupOut(BaseModel):
    """What a teller / cashier sees after scanning or typing a code."""

    order_id: uuid.UUID
    order_code: str
    state: TellerState
    status: OrderStatus
    priority: OrderPriority
    patient_name: str
    patient_age: int | None
    tests: list[str]
    subtotal: int
    discount: int
    total: int
    amount_due: int
    paid: PaidInfo | None
    token: TokenOut | None
    receipt_no_required: bool
    counter_enabled: bool


class ReceiveIn(BaseModel):
    method: Literal["BANK_TELLER", "COUNTER_CASH"] = "BANK_TELLER"
    receipt_no: str | None = Field(default=None, max_length=40)


class ReceiptOut(BaseModel):
    payment_id: uuid.UUID
    order_code: str
    patient_name: str
    amount: int
    method: PaymentMethod
    paid_at: datetime
    receipt_no: str | None
    token: TokenOut


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_id: uuid.UUID
    method: PaymentMethod
    provider: str | None
    method_hint: str | None
    amount: int
    status: PaymentStatus
    status_reason: str | None
    gateway_tran_id: str | None
    provider_txn_id: str | None
    bank_receipt_no: str | None
    received_by_staff_id: uuid.UUID | None
    station: str | None
    paid_at: datetime | None
    reconciliation_status: str
    created_at: datetime


class DayCloseRow(BaseModel):
    payment_id: uuid.UUID
    order_code: str | None
    paid_at: datetime | None
    amount: int
    method: PaymentMethod
    status: PaymentStatus
    receipt_no: str | None
    token: str | None


class DayCloseOut(BaseModel):
    day: date
    staff_id: uuid.UUID
    staff_name: str
    station: str | None
    count: int
    total: int
    refunded_total: int
    net: int
    rows: list[DayCloseRow]


# ---- online payment (patient) ---------------------------------------------------------------------


class PayIn(BaseModel):
    method: Literal["bkash", "nagad", "upay", "rocket", "card"]


class PayOut(BaseModel):
    payment_id: uuid.UUID
    tran_id: str
    redirect_url: str
    amount: int


class PaymentStatusOut(BaseModel):
    tran_id: str
    status: PaymentStatus
    reason: str | None
    amount: int
    order_id: uuid.UUID
    order_code: str | None
    order_status: OrderStatus


class PublicConfig(BaseModel):
    online_payments: bool
    provider: str
    methods: list[str]


# ---- refunds ---------------------------------------------------------------------------------------


class RefundRequestIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RefundApproveIn(BaseModel):
    mode: RefundMode
    manual_reference: str | None = Field(default=None, max_length=80)


class RefundRejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RefundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    payment_id: uuid.UUID
    order_id: uuid.UUID
    amount: int
    reason: str
    status: RefundStatus
    status_reason: str | None
    mode: RefundMode | None
    requested_by: uuid.UUID | None
    decided_by: uuid.UUID | None
    manual_reference: str | None
    created_at: datetime


class RefundRow(RefundOut):
    order_code: str | None
    patient_name: str
    payment_method: PaymentMethod
    provider: str | None


class OrderPayments(BaseModel):
    order_id: uuid.UUID
    order_code: str
    patient_name: str
    total: int
    payments: list[PaymentOut]
    refunds: list[RefundOut]


# ---- reconciliation --------------------------------------------------------------------------------


class MappingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    bank_name: str
    date_column: str
    amount_column: str
    reference_column: str
    receipt_column: str | None
    date_format: str


class ImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    bank_name: str
    filename: str
    rows: int
    matched: int
    exceptions: int
    skipped: int
    created_at: datetime


class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    bank_name: str
    line_no: int
    txn_date: date | None
    amount: int
    reference: str
    receipt_no: str | None
    order_code: str | None
    match: LineMatch
    note: str | None
    created_at: datetime


class ResolveIn(BaseModel):
    note: str = Field(min_length=3, max_length=500)

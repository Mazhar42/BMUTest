"""M3: prescriptions, orders, waivers, payment records

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07 23:19:20.209435+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('payment_event',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('payment_id', sa.Uuid(), nullable=True),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_event'))
    )
    op.create_index(op.f('ix_payment_event_payment_id'), 'payment_event', ['payment_id'], unique=False)
    op.create_table('prescription',
    sa.Column('patient_id', sa.Uuid(), nullable=False),
    sa.Column('images', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('doctor_name', sa.String(length=120), nullable=True),
    sa.Column('prescription_date', sa.Date(), nullable=True),
    sa.Column('status', sa.Enum('DRAFT', 'SUBMITTED', 'NEEDS_CLARIFICATION', 'VERIFIED', 'REJECTED', name='prescriptionstatus', native_enum=False, length=24), nullable=False),
    sa.Column('status_reason', sa.Text(), nullable=True),
    sa.Column('channel', sa.Enum('APP', 'WEB', 'HELPDESK', 'WALKIN', 'KIOSK', 'HOME', 'BACKENTRY', name='channel', native_enum=False, length=32), nullable=False),
    sa.Column('uploaded_by_staff_id', sa.Uuid(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verified_by', sa.Uuid(), nullable=True),
    sa.Column('clarification_note', sa.Text(), nullable=True),
    sa.Column('sla_due_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], name=op.f('fk_prescription_patient_id_patient')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_prescription'))
    )
    op.create_index(op.f('ix_prescription_patient_id'), 'prescription', ['patient_id'], unique=False)
    op.create_table('lab_order',
    sa.Column('order_code', sa.String(length=12), nullable=True),
    sa.Column('patient_id', sa.Uuid(), nullable=False),
    sa.Column('account_id', sa.Uuid(), nullable=True),
    sa.Column('prescription_id', sa.Uuid(), nullable=True),
    sa.Column('channel', sa.Enum('APP', 'WEB', 'HELPDESK', 'WALKIN', 'KIOSK', 'HOME', 'BACKENTRY', name='channel', native_enum=False, length=32), nullable=False),
    sa.Column('status', sa.Enum('DRAFT', 'PENDING_VERIFICATION', 'NEEDS_CLARIFICATION', 'AWAITING_PAYMENT', 'PAID', 'READY_FOR_COLLECTION', 'CHECKED_IN', 'COLLECTED', 'IN_LAB', 'COMPLETED', 'REJECTED', 'EXPIRED', 'CANCELLED', 'REFUND_PENDING', 'REFUNDED', name='orderstatus', native_enum=False, length=32), nullable=False),
    sa.Column('status_reason', sa.Text(), nullable=True),
    sa.Column('priority', sa.Enum('NORMAL', 'ELDERLY', 'DISABLED', 'EMERGENCY', name='orderpriority', native_enum=False, length=16), nullable=False),
    sa.Column('fee_category', sa.Enum('GENERAL', 'FREE', 'POOR_FUND', 'STAFF', 'CONCESSION', name='feecategory', native_enum=False, length=16), nullable=False),
    sa.Column('waiver_approved_by', sa.Uuid(), nullable=True),
    sa.Column('subtotal', sa.Integer(), nullable=False),
    sa.Column('discount', sa.Integer(), nullable=False),
    sa.Column('total', sa.Integer(), nullable=False),
    sa.Column('lang', sa.String(length=2), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('clarification_note', sa.Text(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sla_due_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verified_by_staff_id', sa.Uuid(), nullable=True),
    sa.Column('created_by_staff_id', sa.Uuid(), nullable=True),
    sa.Column('slip_print_count', sa.Integer(), nullable=False),
    sa.Column('pending_verification_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('needs_clarification_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('awaiting_payment_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expired_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('total >= 0 AND discount >= 0 AND discount <= subtotal', name=op.f('ck_lab_order_amounts')),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], name=op.f('fk_lab_order_account_id_account')),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], name=op.f('fk_lab_order_patient_id_patient')),
    sa.ForeignKeyConstraint(['prescription_id'], ['prescription.id'], name=op.f('fk_lab_order_prescription_id_prescription')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_order')),
    sa.UniqueConstraint('order_code', name=op.f('uq_lab_order_order_code'))
    )
    op.create_index(op.f('ix_lab_order_account_id'), 'lab_order', ['account_id'], unique=False)
    op.create_index(op.f('ix_lab_order_patient_id'), 'lab_order', ['patient_id'], unique=False)
    op.create_index('ix_lab_order_queue', 'lab_order', ['status', 'sla_due_at'], unique=False)
    op.create_index(op.f('ix_lab_order_status'), 'lab_order', ['status'], unique=False)
    op.create_index(op.f('ix_lab_order_submitted_at'), 'lab_order', ['submitted_at'], unique=False)
    op.create_table('lab_order_item',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('test_id', sa.Uuid(), nullable=False),
    sa.Column('department_id', sa.Uuid(), nullable=False),
    sa.Column('test_code', sa.String(length=30), nullable=False),
    sa.Column('test_name_en', sa.String(length=160), nullable=False),
    sa.Column('test_name_bn', sa.String(length=160), nullable=False),
    sa.Column('abbreviation', sa.String(length=20), nullable=False),
    sa.Column('price_snapshot', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('ORDERED', 'COLLECTED', 'RECEIVED', 'RESULT_ENTERED', 'VERIFIED', 'RELEASED', 'RECOLLECT_REQUIRED', 'CANCELLED', name='itemstatus', native_enum=False, length=24), nullable=False),
    sa.Column('status_reason', sa.Text(), nullable=True),
    sa.Column('specimen_id', sa.Uuid(), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['department.id'], name=op.f('fk_lab_order_item_department_id_department')),
    sa.ForeignKeyConstraint(['order_id'], ['lab_order.id'], name=op.f('fk_lab_order_item_order_id_lab_order'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_id'], ['lab_test.id'], name=op.f('fk_lab_order_item_test_id_lab_test')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_order_item'))
    )
    op.create_index(op.f('ix_lab_order_item_department_id'), 'lab_order_item', ['department_id'], unique=False)
    op.create_index(op.f('ix_lab_order_item_order_id'), 'lab_order_item', ['order_id'], unique=False)
    op.create_table('payment',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('method', sa.Enum('GATEWAY', 'BANK_TELLER', 'COUNTER_CASH', 'WAIVER', name='paymentmethod', native_enum=False, length=16), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=True),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('INITIATED', 'PENDING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED', 'REFUND_PENDING', 'REFUNDED', name='paymentstatus', native_enum=False, length=16), nullable=False),
    sa.Column('status_reason', sa.Text(), nullable=True),
    sa.Column('gateway_tran_id', sa.String(length=40), nullable=True),
    sa.Column('provider_txn_id', sa.String(length=80), nullable=True),
    sa.Column('bank_receipt_no', sa.String(length=40), nullable=True),
    sa.Column('received_by_staff_id', sa.Uuid(), nullable=True),
    sa.Column('approved_by_staff_id', sa.Uuid(), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('success_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reconciliation_status', sa.String(length=16), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['lab_order.id'], name=op.f('fk_payment_order_id_lab_order')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payment')),
    sa.UniqueConstraint('gateway_tran_id', name=op.f('uq_payment_gateway_tran_id')),
    sa.UniqueConstraint('provider', 'provider_txn_id', name=op.f('uq_payment_provider_provider_txn_id'))
    )
    op.create_index(op.f('ix_payment_order_id'), 'payment', ['order_id'], unique=False)
    op.create_table('waiver_request',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('fee_category', sa.Enum('GENERAL', 'FREE', 'POOR_FUND', 'STAFF', 'CONCESSION', name='feecategory', native_enum=False, length=16), nullable=False),
    sa.Column('requested_by', sa.Uuid(), nullable=False),
    sa.Column('request_reason', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('REQUESTED', 'APPROVED', 'DECLINED', 'WITHDRAWN', name='waiverstatus', native_enum=False, length=12), nullable=False),
    sa.Column('status_reason', sa.Text(), nullable=True),
    sa.Column('decided_by', sa.Uuid(), nullable=True),
    sa.Column('approved_discount', sa.Integer(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('declined_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['lab_order.id'], name=op.f('fk_waiver_request_order_id_lab_order'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_waiver_request'))
    )
    op.create_index(op.f('ix_waiver_request_order_id'), 'waiver_request', ['order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_waiver_request_order_id'), table_name='waiver_request')
    op.drop_table('waiver_request')
    op.drop_index(op.f('ix_payment_order_id'), table_name='payment')
    op.drop_table('payment')
    op.drop_index(op.f('ix_lab_order_item_order_id'), table_name='lab_order_item')
    op.drop_index(op.f('ix_lab_order_item_department_id'), table_name='lab_order_item')
    op.drop_table('lab_order_item')
    op.drop_index(op.f('ix_lab_order_submitted_at'), table_name='lab_order')
    op.drop_index(op.f('ix_lab_order_status'), table_name='lab_order')
    op.drop_index('ix_lab_order_queue', table_name='lab_order')
    op.drop_index(op.f('ix_lab_order_patient_id'), table_name='lab_order')
    op.drop_index(op.f('ix_lab_order_account_id'), table_name='lab_order')
    op.drop_table('lab_order')
    op.drop_index(op.f('ix_prescription_patient_id'), table_name='prescription')
    op.drop_table('prescription')
    op.drop_index(op.f('ix_payment_event_payment_id'), table_name='payment_event')
    op.drop_table('payment_event')

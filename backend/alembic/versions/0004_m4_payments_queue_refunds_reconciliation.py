"""M4 payments queue refunds reconciliation

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-23 22:13:09.881054+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('bank_column_mapping',
    sa.Column('bank_name', sa.String(length=80), nullable=False),
    sa.Column('date_column', sa.String(length=80), nullable=False),
    sa.Column('amount_column', sa.String(length=80), nullable=False),
    sa.Column('reference_column', sa.String(length=80), nullable=False),
    sa.Column('receipt_column', sa.String(length=80), nullable=True),
    sa.Column('date_format', sa.String(length=20), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_bank_column_mapping')),
    sa.UniqueConstraint('bank_name', name=op.f('uq_bank_column_mapping_bank_name'))
    )
    op.create_table('bank_statement_import',
    sa.Column('bank_name', sa.String(length=80), nullable=False),
    sa.Column('filename', sa.String(length=200), nullable=False),
    sa.Column('uploaded_by', sa.Uuid(), nullable=True),
    sa.Column('rows', sa.Integer(), nullable=False),
    sa.Column('matched', sa.Integer(), nullable=False),
    sa.Column('exceptions', sa.Integer(), nullable=False),
    sa.Column('skipped', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_bank_statement_import'))
    )
    op.create_table('queue_token',
    sa.Column('token_date', sa.Date(), nullable=False),
    sa.Column('queue', sa.Enum('A', 'W', 'P', name='queuename', native_enum=False), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('ISSUED', 'CALLED', 'SERVED', 'NO_SHOW', 'CANCELLED', name='tokenstatus', native_enum=False, length=12), nullable=False),
    sa.Column('status_reason', sa.String(length=300), nullable=True),
    sa.Column('issued_by', sa.Uuid(), nullable=True),
    sa.Column('called_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('served_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('station_no', sa.String(length=20), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['lab_order.id'], name=op.f('fk_queue_token_order_id_lab_order')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_queue_token')),
    sa.UniqueConstraint('token_date', 'queue', 'number', name=op.f('uq_queue_token_token_date_queue_number'))
    )
    op.create_index(op.f('ix_queue_token_order_id'), 'queue_token', ['order_id'], unique=False)
    op.create_index(op.f('ix_queue_token_token_date'), 'queue_token', ['token_date'], unique=False)
    op.create_table('bank_statement_line',
    sa.Column('import_id', sa.Uuid(), nullable=False),
    sa.Column('bank_name', sa.String(length=80), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('line_no', sa.Integer(), nullable=False),
    sa.Column('txn_date', sa.Date(), nullable=True),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('reference', sa.Text(), nullable=False),
    sa.Column('receipt_no', sa.String(length=80), nullable=True),
    sa.Column('order_code', sa.String(length=12), nullable=True),
    sa.Column('match', sa.Enum('MATCHED', 'UNMATCHED', 'AMOUNT_MISMATCH', 'DUPLICATE', 'RESOLVED', name='linematch', native_enum=False, length=16), nullable=False),
    sa.Column('matched_payment_id', sa.Uuid(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('resolved_by', sa.Uuid(), nullable=True),
    sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['import_id'], ['bank_statement_import.id'], name=op.f('fk_bank_statement_line_import_id_bank_statement_import'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['matched_payment_id'], ['payment.id'], name=op.f('fk_bank_statement_line_matched_payment_id_payment')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_bank_statement_line')),
    sa.UniqueConstraint('bank_name', 'fingerprint', name=op.f('uq_bank_statement_line_bank_name_fingerprint'))
    )
    op.create_index(op.f('ix_bank_statement_line_import_id'), 'bank_statement_line', ['import_id'], unique=False)
    op.create_index(op.f('ix_bank_statement_line_match'), 'bank_statement_line', ['match'], unique=False)
    op.create_index(op.f('ix_bank_statement_line_order_code'), 'bank_statement_line', ['order_code'], unique=False)
    op.create_table('refund',
    sa.Column('payment_id', sa.Uuid(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('REQUESTED', 'APPROVED', 'COMPLETED', 'REJECTED', 'FAILED', name='refundstatus', native_enum=False, length=12), nullable=False),
    sa.Column('status_reason', sa.Text(), nullable=True),
    sa.Column('mode', sa.Enum('PROVIDER', 'MANUAL', name='refundmode', native_enum=False, length=10), nullable=True),
    sa.Column('requested_by', sa.Uuid(), nullable=True),
    sa.Column('decided_by', sa.Uuid(), nullable=True),
    sa.Column('manual_reference', sa.String(length=80), nullable=True),
    sa.Column('provider_ref_id', sa.String(length=80), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['lab_order.id'], name=op.f('fk_refund_order_id_lab_order')),
    sa.ForeignKeyConstraint(['payment_id'], ['payment.id'], name=op.f('fk_refund_payment_id_payment')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_refund'))
    )
    op.create_index(op.f('ix_refund_order_id'), 'refund', ['order_id'], unique=False)
    op.create_index(op.f('ix_refund_payment_id'), 'refund', ['payment_id'], unique=False)
    op.add_column('payment', sa.Column('method_hint', sa.String(length=20), nullable=True))
    op.add_column('payment', sa.Column('redirect_url', sa.Text(), nullable=True))
    op.add_column('payment', sa.Column('station', sa.String(length=60), nullable=True))
    op.add_column('payment', sa.Column('pending_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment', sa.Column('expired_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment', sa.Column('refund_pending_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment', sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment', sa.Column('reconciliation_note', sa.Text(), nullable=True))
    op.create_index('ix_payment_method_paid', 'payment', ['method', 'paid_at'], unique=False)
    op.create_index(op.f('ix_payment_received_by_staff_id'), 'payment', ['received_by_staff_id'], unique=False)
    op.create_index(op.f('ix_payment_status'), 'payment', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payment_status'), table_name='payment')
    op.drop_index(op.f('ix_payment_received_by_staff_id'), table_name='payment')
    op.drop_index('ix_payment_method_paid', table_name='payment')
    op.drop_column('payment', 'reconciliation_note')
    op.drop_column('payment', 'refunded_at')
    op.drop_column('payment', 'refund_pending_at')
    op.drop_column('payment', 'expired_at')
    op.drop_column('payment', 'cancelled_at')
    op.drop_column('payment', 'pending_at')
    op.drop_column('payment', 'station')
    op.drop_column('payment', 'redirect_url')
    op.drop_column('payment', 'method_hint')
    op.drop_index(op.f('ix_refund_payment_id'), table_name='refund')
    op.drop_index(op.f('ix_refund_order_id'), table_name='refund')
    op.drop_table('refund')
    op.drop_index(op.f('ix_bank_statement_line_order_code'), table_name='bank_statement_line')
    op.drop_index(op.f('ix_bank_statement_line_match'), table_name='bank_statement_line')
    op.drop_index(op.f('ix_bank_statement_line_import_id'), table_name='bank_statement_line')
    op.drop_table('bank_statement_line')
    op.drop_index(op.f('ix_queue_token_token_date'), table_name='queue_token')
    op.drop_index(op.f('ix_queue_token_order_id'), table_name='queue_token')
    op.drop_table('queue_token')
    op.drop_table('bank_statement_import')
    op.drop_table('bank_column_mapping')

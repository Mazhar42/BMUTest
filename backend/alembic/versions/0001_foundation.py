"""foundation

Revision ID: 0001
Revises: 
Create Date: 2026-10-02 15:48:12.583047+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('audit_log',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor_type', sa.String(length=16), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('actor_label', sa.String(length=120), nullable=True),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=True),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('patient_id', sa.Uuid(), nullable=True),
    sa.Column('before', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('after', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=300), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_log'))
    )
    op.create_index(op.f('ix_audit_log_action'), 'audit_log', ['action'], unique=False)
    op.create_index(op.f('ix_audit_log_actor_id'), 'audit_log', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_log_at'), 'audit_log', ['at'], unique=False)
    op.create_index('ix_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_audit_log_patient_id'), 'audit_log', ['patient_id'], unique=False)
    op.create_table('daily_counter',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('value', sa.BigInteger(), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_daily_counter'))
    )
    op.create_table('device',
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('kind', sa.Enum('DISPLAY', 'KIOSK', 'ANALYZER', name='devicekind', native_enum=False, length=32), nullable=False),
    sa.Column('queue_id', sa.String(length=40), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_device')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_device_token_hash'))
    )
    op.create_table('domain_event',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('from_status', sa.String(length=40), nullable=True),
    sa.Column('to_status', sa.String(length=40), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=True),
    sa.Column('actor_type', sa.String(length=16), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_domain_event'))
    )
    op.create_index(op.f('ix_domain_event_at'), 'domain_event', ['at'], unique=False)
    op.create_index('ix_domain_event_entity', 'domain_event', ['entity_type', 'to_status', 'at'], unique=False)
    op.create_index(op.f('ix_domain_event_order_id'), 'domain_event', ['order_id'], unique=False)
    op.create_table('setting',
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_setting')),
    sa.UniqueConstraint('key', name=op.f('uq_setting_key'))
    )
    op.create_table('staff',
    sa.Column('username', sa.String(length=60), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('full_name_bn', sa.String(length=120), nullable=True),
    sa.Column('designation', sa.String(length=120), nullable=True),
    sa.Column('mobile', sa.String(length=20), nullable=True),
    sa.Column('password_hash', sa.String(length=200), nullable=False),
    sa.Column('pin_hash', sa.String(length=200), nullable=True),
    sa.Column('totp_secret', sa.String(length=512), nullable=True),
    sa.Column('totp_pending_secret', sa.String(length=512), nullable=True),
    sa.Column('totp_enabled', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('failed_logins', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('preferred_language', sa.String(length=2), nullable=False),
    sa.Column('must_change_password', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_staff')),
    sa.UniqueConstraint('username', name=op.f('uq_staff_username'))
    )
    op.create_table('staff_role',
    sa.Column('staff_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.Enum('HELP_DESK', 'VERIFIER', 'BANK_TELLER', 'CASHIER', 'COLLECTOR', 'LAB_RECEPTION', 'TECHNICIAN', 'PATHOLOGIST', 'REPORT_DESK', 'WAIVER_APPROVER', 'LAB_ADMIN', 'AUDITOR', 'SUPER_ADMIN', 'HOME_COLLECTOR', name='role', native_enum=False, length=32), nullable=False),
    sa.Column('department_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], name=op.f('fk_staff_role_staff_id_staff'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_staff_role')),
    sa.UniqueConstraint('staff_id', 'role', 'department_id', name=op.f('uq_staff_role_staff_id_role_department_id'))
    )
    op.create_index(op.f('ix_staff_role_staff_id'), 'staff_role', ['staff_id'], unique=False)
    op.create_table('staff_session',
    sa.Column('staff_id', sa.Uuid(), nullable=False),
    sa.Column('station', sa.String(length=60), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=300), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], name=op.f('fk_staff_session_staff_id_staff'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_staff_session'))
    )
    op.create_index(op.f('ix_staff_session_staff_id'), 'staff_session', ['staff_id'], unique=False)

    # Append-only audit log: UPDATE/DELETE fail at the database level (ROADMAP §7.1, M1 acceptance).
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_log_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only (% blocked)', TG_OP USING ERRCODE = 'insufficient_privilege';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER audit_log_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update_delete ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_append_only()")
    op.drop_index(op.f('ix_staff_session_staff_id'), table_name='staff_session')
    op.drop_table('staff_session')
    op.drop_index(op.f('ix_staff_role_staff_id'), table_name='staff_role')
    op.drop_table('staff_role')
    op.drop_table('staff')
    op.drop_table('setting')
    op.drop_index(op.f('ix_domain_event_order_id'), table_name='domain_event')
    op.drop_index('ix_domain_event_entity', table_name='domain_event')
    op.drop_index(op.f('ix_domain_event_at'), table_name='domain_event')
    op.drop_table('domain_event')
    op.drop_table('device')
    op.drop_table('daily_counter')
    op.drop_index(op.f('ix_audit_log_patient_id'), table_name='audit_log')
    op.drop_index('ix_audit_log_entity', table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_actor_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_action'), table_name='audit_log')
    op.drop_table('audit_log')

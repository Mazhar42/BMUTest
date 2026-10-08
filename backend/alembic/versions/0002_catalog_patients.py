"""M2: catalog, patients, patient OTP login, SMS outbox

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07 23:19:20.209435+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pg_trgm powers alias search ("s creat" → Creatinine) and patient name search.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table('account',
    sa.Column('mobile', sa.String(length=16), nullable=False),
    sa.Column('preferred_language', sa.String(length=2), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_account')),
    sa.UniqueConstraint('mobile', name=op.f('uq_account_mobile'))
    )
    op.create_table('department',
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name_en', sa.String(length=120), nullable=False),
    sa.Column('name_bn', sa.String(length=120), nullable=False),
    sa.Column('result_mode', sa.Enum('STRUCTURED', 'PDF_UPLOAD', name='resultmode', native_enum=False, length=32), nullable=False),
    sa.Column('report_signatory_staff_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('sort', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_department')),
    sa.UniqueConstraint('code', name=op.f('uq_department_code'))
    )
    op.create_table('notification',
    sa.Column('channel', sa.String(length=10), nullable=False),
    sa.Column('template_key', sa.String(length=60), nullable=False),
    sa.Column('lang', sa.String(length=2), nullable=False),
    sa.Column('to', sa.String(length=20), nullable=False),
    sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'SENT', 'FAILED', name='notificationstatus', native_enum=False, length=10), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.String(length=300), nullable=True),
    sa.Column('provider_msg_id', sa.String(length=80), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('order_id', sa.Uuid(), nullable=True),
    sa.Column('patient_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notification'))
    )
    op.create_index(op.f('ix_notification_order_id'), 'notification', ['order_id'], unique=False)
    op.create_index(op.f('ix_notification_patient_id'), 'notification', ['patient_id'], unique=False)
    op.create_index('ix_notification_pending', 'notification', ['status', 'next_attempt_at'], unique=False)
    op.create_table('otp_challenge',
    sa.Column('mobile', sa.String(length=16), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('requester_ip', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_otp_challenge'))
    )
    op.create_index(op.f('ix_otp_challenge_mobile'), 'otp_challenge', ['mobile'], unique=False)
    op.create_index(op.f('ix_otp_challenge_requester_ip'), 'otp_challenge', ['requester_ip'], unique=False)
    op.create_table('lab_test',
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name_en', sa.String(length=160), nullable=False),
    sa.Column('name_bn', sa.String(length=160), nullable=False),
    sa.Column('abbreviation', sa.String(length=20), nullable=False),
    sa.Column('aliases', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('search_text', sa.Text(), nullable=False),
    sa.Column('department_id', sa.Uuid(), nullable=False),
    sa.Column('specimen_type', sa.Enum('BLOOD', 'URINE', 'STOOL', 'SWAB', 'OTHER', name='specimentype', native_enum=False, length=32), nullable=False),
    sa.Column('container_type', sa.Enum('EDTA', 'PLAIN', 'SST', 'FLUORIDE', 'CITRATE', 'HEPARIN', 'URINE_CUP', 'STOOL_CUP', 'BLOOD_CULTURE', 'SWAB_TUBE', 'OTHER', name='containertype', native_enum=False, length=32), nullable=False),
    sa.Column('collection_resource', sa.Enum('BLOOD_COLLECTION', 'URINE', 'SPECIAL', name='collectionresource', native_enum=False, length=24), nullable=False),
    sa.Column('fasting_required', sa.Boolean(), nullable=False),
    sa.Column('fasting_hours', sa.Integer(), nullable=True),
    sa.Column('prep_en', sa.Text(), nullable=True),
    sa.Column('prep_bn', sa.Text(), nullable=True),
    sa.Column('tat_hours', sa.Integer(), nullable=False),
    sa.Column('requires_prescription', sa.Boolean(), nullable=False),
    sa.Column('home_collectable', sa.Boolean(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('sort', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['department.id'], name=op.f('fk_lab_test_department_id_department')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_test')),
    sa.UniqueConstraint('code', name=op.f('uq_lab_test_code'))
    )
    op.create_index(op.f('ix_lab_test_department_id'), 'lab_test', ['department_id'], unique=False)
    op.create_index('ix_lab_test_search_trgm', 'lab_test', ['search_text'], unique=False, postgresql_using='gin', postgresql_ops={'search_text': 'gin_trgm_ops'})
    op.create_table('patient',
    sa.Column('account_id', sa.Uuid(), nullable=True),
    sa.Column('hospital_patient_no', sa.String(length=40), nullable=True),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('full_name_bn', sa.String(length=120), nullable=True),
    sa.Column('sex', sa.Enum('M', 'F', 'O', name='sex', native_enum=False), nullable=False),
    sa.Column('date_of_birth', sa.Date(), nullable=True),
    sa.Column('age_years', sa.Integer(), nullable=True),
    sa.Column('age_estimated', sa.Boolean(), nullable=False),
    sa.Column('mobile', sa.String(length=16), nullable=True),
    sa.Column('nid', sa.String(length=512), nullable=True),
    sa.Column('relation_to_account', sa.Enum('SELF', 'SPOUSE', 'CHILD', 'PARENT', 'SIBLING', 'OTHER', name='relation', native_enum=False, length=32), nullable=False),
    sa.Column('created_channel', sa.Enum('APP', 'WEB', 'HELPDESK', 'WALKIN', 'KIOSK', 'HOME', 'BACKENTRY', name='channel', native_enum=False, length=32), nullable=False),
    sa.Column('created_by_staff_id', sa.Uuid(), nullable=True),
    sa.Column('name_search', sa.String(length=260), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], name=op.f('fk_patient_account_id_account')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_patient'))
    )
    op.create_index(op.f('ix_patient_account_id'), 'patient', ['account_id'], unique=False)
    op.create_index(op.f('ix_patient_hospital_patient_no'), 'patient', ['hospital_patient_no'], unique=False)
    op.create_index(op.f('ix_patient_mobile'), 'patient', ['mobile'], unique=False)
    op.create_index('ix_patient_name_trgm', 'patient', ['name_search'], unique=False, postgresql_using='gin', postgresql_ops={'name_search': 'gin_trgm_ops'})
    op.create_table('patient_refresh_token',
    sa.Column('account_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('family_id', sa.Uuid(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], name=op.f('fk_patient_refresh_token_account_id_account'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_patient_refresh_token')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_patient_refresh_token_token_hash'))
    )
    op.create_index(op.f('ix_patient_refresh_token_account_id'), 'patient_refresh_token', ['account_id'], unique=False)
    op.create_index(op.f('ix_patient_refresh_token_family_id'), 'patient_refresh_token', ['family_id'], unique=False)
    op.create_table('lab_test_price',
    sa.Column('test_id', sa.Uuid(), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('fee_category', sa.Enum('GENERAL', 'FREE', 'POOR_FUND', 'STAFF', 'CONCESSION', name='feecategory', native_enum=False, length=32), nullable=False),
    sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
    sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['test_id'], ['lab_test.id'], name=op.f('fk_lab_test_price_test_id_lab_test'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_test_price'))
    )
    op.create_index(op.f('ix_lab_test_price_test_id'), 'lab_test_price', ['test_id'], unique=False)
    op.create_table('test_parameter',
    sa.Column('test_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('unit', sa.String(length=30), nullable=True),
    sa.Column('decimals', sa.Integer(), nullable=False),
    sa.Column('sort', sa.Integer(), nullable=False),
    sa.Column('value_type', sa.Enum('NUMERIC', 'TEXT', 'OPTION', name='valuetype', native_enum=False, length=32), nullable=False),
    sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('critical_low', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('critical_high', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('analyzer_code', sa.String(length=40), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['test_id'], ['lab_test.id'], name=op.f('fk_test_parameter_test_id_lab_test'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_test_parameter')),
    sa.UniqueConstraint('test_id', 'code', name=op.f('uq_test_parameter_test_id_code'))
    )
    op.create_index(op.f('ix_test_parameter_analyzer_code'), 'test_parameter', ['analyzer_code'], unique=False)
    op.create_index(op.f('ix_test_parameter_test_id'), 'test_parameter', ['test_id'], unique=False)
    op.create_table('reference_range',
    sa.Column('parameter_id', sa.Uuid(), nullable=False),
    sa.Column('sex', sa.String(length=1), nullable=True),
    sa.Column('age_min_days', sa.Integer(), nullable=True),
    sa.Column('age_max_days', sa.Integer(), nullable=True),
    sa.Column('low', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('high', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('text', sa.String(length=200), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['parameter_id'], ['test_parameter.id'], name=op.f('fk_reference_range_parameter_id_test_parameter'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reference_range'))
    )
    op.create_index(op.f('ix_reference_range_parameter_id'), 'reference_range', ['parameter_id'], unique=False)
    op.create_foreign_key(op.f('fk_staff_role_department_id_department'), 'staff_role', 'department', ['department_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(op.f('fk_staff_role_department_id_department'), 'staff_role', type_='foreignkey')
    op.drop_index(op.f('ix_reference_range_parameter_id'), table_name='reference_range')
    op.drop_table('reference_range')
    op.drop_index(op.f('ix_test_parameter_test_id'), table_name='test_parameter')
    op.drop_index(op.f('ix_test_parameter_analyzer_code'), table_name='test_parameter')
    op.drop_table('test_parameter')
    op.drop_index(op.f('ix_lab_test_price_test_id'), table_name='lab_test_price')
    op.drop_table('lab_test_price')
    op.drop_index(op.f('ix_patient_refresh_token_family_id'), table_name='patient_refresh_token')
    op.drop_index(op.f('ix_patient_refresh_token_account_id'), table_name='patient_refresh_token')
    op.drop_table('patient_refresh_token')
    op.drop_index('ix_patient_name_trgm', table_name='patient', postgresql_using='gin', postgresql_ops={'name_search': 'gin_trgm_ops'})
    op.drop_index(op.f('ix_patient_mobile'), table_name='patient')
    op.drop_index(op.f('ix_patient_hospital_patient_no'), table_name='patient')
    op.drop_index(op.f('ix_patient_account_id'), table_name='patient')
    op.drop_table('patient')
    op.drop_index('ix_lab_test_search_trgm', table_name='lab_test', postgresql_using='gin', postgresql_ops={'search_text': 'gin_trgm_ops'})
    op.drop_index(op.f('ix_lab_test_department_id'), table_name='lab_test')
    op.drop_table('lab_test')
    op.drop_index(op.f('ix_otp_challenge_requester_ip'), table_name='otp_challenge')
    op.drop_index(op.f('ix_otp_challenge_mobile'), table_name='otp_challenge')
    op.drop_table('otp_challenge')
    op.drop_index('ix_notification_pending', table_name='notification')
    op.drop_index(op.f('ix_notification_patient_id'), table_name='notification')
    op.drop_index(op.f('ix_notification_order_id'), table_name='notification')
    op.drop_table('notification')
    op.drop_table('department')
    op.drop_table('account')

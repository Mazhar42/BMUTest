"""Static configuration from environment variables (.env). Runtime-tunable values live in the
`setting` table (see app.core.settings_store) and fall back to these defaults."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    public_base_url: str = "http://localhost:5173"
    staff_base_url: str = "http://localhost:5174/staff"
    api_base_url: str = "http://localhost:18000"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:5174"])

    database_url: str = "postgresql+psycopg://bmu:bmu@localhost:55432/bmu"
    test_database_url: str = "postgresql+psycopg://bmu:bmu@localhost:55432/bmu_test"
    redis_url: str = "redis://localhost:56379/0"
    celery_enabled: bool = False

    jwt_secret: str = "dev-only-change-me-dev-only-change-me"  # rejected in prod (check_production)
    app_encryption_key: str = "2BnaXi43ui3u9V6P6smjhJdmEbs8ugB5oUW6aM0oXA8="  # Fernet key, dev only

    # Staff auth (ROADMAP §6.4)
    staff_session_hours: int = 12
    staff_idle_lock_minutes: int = 30
    staff_max_failed_logins: int = 5
    staff_lockout_minutes: int = 15
    # Patient auth
    patient_access_token_minutes: int = 15
    patient_refresh_token_days: int = 30
    cookie_secure: bool = False
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_send_limit_per_mobile: int = 3
    otp_send_window_minutes: int = 15
    otp_send_limit_per_ip: int = 20

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: str = "./storage"
    s3_endpoint: str = "http://localhost:59000"
    s3_public_endpoint: str = "http://localhost:59000"
    s3_access_key: str = "bmuminio"
    s3_secret_key: str = "bmuminio-secret"
    s3_region: str = "us-east-1"
    presign_seconds: int = 300

    # SMS
    sms_provider: Literal["mock", "sslwireless"] = "mock"
    sms_api_url: str = ""
    sms_api_token: str = ""
    sms_sender_id: str = "BMU LAB"

    # Payments
    payment_provider: Literal["mock", "sslcommerz", "bkash"] = "mock"
    sslcommerz_store_id: str = ""
    sslcommerz_store_password: str = ""
    sslcommerz_sandbox: bool = True
    bkash_app_key: str = ""
    bkash_app_secret: str = ""
    bkash_username: str = ""
    bkash_password: str = ""
    bkash_sandbox: bool = True
    payment_pending_requery_minutes: int = 10
    counter_payment_enabled: bool = False
    teller_require_receipt_no: bool = False

    # Orders / verification
    verification_sla_hours: int = 4
    order_expiry_days: int = 7

    # Codes & specimens (ROADMAP §4)
    tube_grouping: Literal["container", "container_department"] = "container"
    require_paper_hospital_copy: bool = False
    print_bank_copy_when_paid: bool = False
    slip_account_head: str = "PLACEHOLDER — account head to be confirmed by BMU"

    # Scheduling (ROADMAP §5, M5)
    slot_hold_minutes: int = 15
    slot_horizon_days: int = 14
    fasting_last_window_end: str = "11:00"
    reschedule_max: int = 2
    reschedule_cutoff_hours: int = 2
    allow_unpaid_booking_pct: int = 0
    checkin_early_minutes: int = 30
    checkin_late_minutes: int = 30
    reminder_hour_local: int = 18
    queue_ratio_a: int = 2
    queue_ratio_w: int = 1

    # Results / reports
    release_by_enterer_allowed: bool = False
    share_link_days: int = 7
    institution_name_en: str = "Bangabandhu Sheikh Mujib Medical University"
    institution_name_bn: str = "বঙ্গবন্ধু শেখ মুজিব মেডিকেল বিশ্ববিদ্যালয়"
    lab_name_en: str = "Department of Laboratory Medicine"
    lab_name_bn: str = "ল্যাবরেটরি মেডিসিন বিভাগ"
    institution_address: str = "Shahbag, Dhaka-1000"

    # M10 (post-pilot) — all off by default
    ocr_provider: Literal["none", "mock", "tesseract"] = "none"
    web_push_enabled: bool = False
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:lab@example.org"
    pades_enabled: bool = False
    pades_p12_path: str = ""
    pades_p12_password: str = ""
    home_collection_enabled: bool = False
    home_collection_fee_paisa: int = 0
    analyzer_token: str = ""
    fhir_profile_base: str = "https://fhir.dghs.gov.bd/core/StructureDefinition"
    shr_endpoint: str = ""


DEV_JWT_SECRET = "dev-only-change-me-dev-only-change-me"
DEV_ENCRYPTION_KEY = "2BnaXi43ui3u9V6P6smjhJdmEbs8ugB5oUW6aM0oXA8="


def check_production(s: Settings) -> list[str]:
    """Settings that must never reach production with their development defaults."""
    problems = []
    if s.jwt_secret == DEV_JWT_SECRET or len(s.jwt_secret) < 32:
        problems.append("JWT_SECRET must be a new random value of 32+ characters")
    if s.app_encryption_key == DEV_ENCRYPTION_KEY:
        problems.append("APP_ENCRYPTION_KEY must be a newly generated Fernet key")
    if not s.cookie_secure:
        problems.append("COOKIE_SECURE must be true (HTTPS only)")
    if s.s3_secret_key == "bmuminio-secret":
        problems.append("S3_SECRET_KEY must not be the development default")
    return problems


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.env == "prod" and (problems := check_production(s)):
        raise RuntimeError("Refusing to start in prod: " + "; ".join(problems))
    return s

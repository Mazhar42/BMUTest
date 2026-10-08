from __future__ import annotations

from app.config import Settings, check_production


def test_dev_defaults_are_rejected_for_production() -> None:
    problems = check_production(Settings(env="prod"))
    assert any("JWT_SECRET" in p for p in problems)
    assert any("APP_ENCRYPTION_KEY" in p for p in problems)
    assert any("COOKIE_SECURE" in p for p in problems)


def test_proper_production_settings_pass() -> None:
    s = Settings(
        env="prod",
        jwt_secret="x" * 48,
        app_encryption_key="q3Yl8J0v3hS1m0Gm1o7pYb9kq4w8bqH0d2y6cXlP6uE=",
        cookie_secure=True,
        s3_secret_key="a-real-secret",
    )
    assert check_production(s) == []

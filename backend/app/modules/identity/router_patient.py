"""Patient OTP login and token refresh. The refresh token lives only in an httpOnly cookie scoped to
/api/v1/patient/auth; refresh/logout additionally require the X-Requested-With header (CSRF)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Header, Request, Response

from app.config import get_settings
from app.core.errors import Forbidden
from app.deps import DB, client_ip
from app.modules.identity import patient_auth, schemas

router = APIRouter(prefix="/patient/auth", tags=["patient-auth"])

COOKIE = "bmu_refresh"
COOKIE_PATH = "/api/v1/patient/auth"


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE,
        token,
        max_age=s.patient_refresh_token_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )


def _csrf(x_requested_with: str | None) -> None:
    if x_requested_with != "bmu":
        raise Forbidden("CSRF_HEADER_MISSING")


@router.post("/otp/request", response_model=schemas.OtpRequestOut)
def request_otp(data: schemas.OtpRequestIn, db: DB, request: Request) -> schemas.OtpRequestOut:
    sent = patient_auth.request_otp(db, data.mobile, client_ip(request), data.lang)
    db.commit()
    return schemas.OtpRequestOut(
        mobile=sent.mobile, expires_in=sent.expires_in, resend_after=sent.resend_after, debug_code=sent.debug_code
    )


@router.post("/otp/verify", response_model=schemas.PatientTokenOut)
def verify_otp(data: schemas.OtpVerifyIn, db: DB, response: Response) -> schemas.PatientTokenOut:
    try:
        tokens = patient_auth.verify_otp(db, data.mobile, data.code, data.lang)
    finally:
        db.commit()  # keep the attempt counter even when the code is wrong
    _set_cookie(response, tokens.refresh_token)
    return schemas.PatientTokenOut(
        access_token=tokens.access_token, expires_in=tokens.expires_in, account_id=tokens.account.id
    )


@router.post("/refresh", response_model=schemas.PatientTokenOut)
def refresh(
    db: DB,
    response: Response,
    bmu_refresh: Annotated[str | None, Cookie()] = None,
    x_requested_with: Annotated[str | None, Header()] = None,
) -> schemas.PatientTokenOut:
    _csrf(x_requested_with)
    try:
        tokens = patient_auth.refresh(db, bmu_refresh)
    finally:
        db.commit()  # a detected reuse revokes the family even though the call fails
    _set_cookie(response, tokens.refresh_token)
    return schemas.PatientTokenOut(
        access_token=tokens.access_token, expires_in=tokens.expires_in, account_id=tokens.account.id
    )


@router.post("/logout", status_code=204)
def logout(
    db: DB,
    response: Response,
    bmu_refresh: Annotated[str | None, Cookie()] = None,
    x_requested_with: Annotated[str | None, Header()] = None,
) -> None:
    _csrf(x_requested_with)
    patient_auth.logout(db, bmu_refresh)
    db.commit()
    response.delete_cookie(COOKIE, path=COOKIE_PATH)

"""Structured JSON logging with PII masking (mobile numbers, OTPs, names/NID in `extra`)."""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

from app.core import clock

_MOBILE = re.compile(r"(?<!\d)(\+?880|0)?1[3-9]\d{8}(?!\d)")
_OTP = re.compile(r"(?i)(otp|code)([\"'\s:=]+)(\d{4,8})")
_SENSITIVE_KEYS = {"mobile", "to", "full_name", "full_name_bn", "nid", "password", "otp", "totp", "name"}


def mask_text(text: str) -> str:
    text = _MOBILE.sub(lambda m: m.group(0)[:-8] + "*****" + m.group(0)[-3:], text)
    return _OTP.sub(lambda m: f"{m.group(1)}{m.group(2)}******", text)


def mask_value(key: str, value: Any) -> Any:
    if key.lower() in _SENSITIVE_KEYS and isinstance(value, str) and value:
        return value[:2] + "***"
    if isinstance(value, str):
        return mask_text(value)
    return value


class JsonFormatter(logging.Formatter):
    _std = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": clock.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": mask_text(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in self._std and not key.startswith("_"):
                payload[key] = mask_value(key, value)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel("WARNING")

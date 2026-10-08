"""Cursor pagination over (created_at, id) descending (ROADMAP §6.3)."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Select, and_, or_

from app.core.errors import Invalid


class PageMeta(BaseModel):
    next_cursor: str | None = None


def encode_cursor(created_at: datetime, id_: uuid.UUID | int) -> str:
    raw = f"{created_at.isoformat()}|{id_}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        ts, id_ = base64.urlsafe_b64decode(padded).decode().split("|", 1)
        return datetime.fromisoformat(ts), id_
    except Exception as exc:
        raise Invalid("BAD_CURSOR") from exc


def apply_cursor(stmt: Select[Any], created_col: Any, id_col: Any, cursor: str | None, limit: int) -> Select[Any]:
    if cursor:
        ts, raw = decode_cursor(cursor)
        try:
            pytype = id_col.type.python_type
        except NotImplementedError:
            pytype = str
        try:
            id_val: Any = uuid.UUID(raw) if pytype is uuid.UUID else int(raw) if pytype is int else raw
        except ValueError as exc:
            raise Invalid("BAD_CURSOR") from exc
        stmt = stmt.where(or_(created_col < ts, and_(created_col == ts, id_col < id_val)))
    return stmt.order_by(created_col.desc(), id_col.desc()).limit(limit + 1)


def page[T](rows: list[T], limit: int, key: Any) -> tuple[list[T], str | None]:
    """Trim the +1 look-ahead row and build the next cursor with `key(row) -> (created_at, id)`."""
    if len(rows) > limit:
        rows = rows[:limit]
        created, id_ = key(rows[-1])
        return rows, encode_cursor(created, id_)
    return rows, None

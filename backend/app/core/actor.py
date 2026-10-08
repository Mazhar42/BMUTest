"""Who is acting. Set per request by the auth dependencies; background jobs use SYSTEM."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal

ActorType = Literal["staff", "patient", "system", "gateway", "device", "public"]


@dataclass(frozen=True)
class Actor:
    type: ActorType
    id: uuid.UUID | None = None
    label: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)
    department_ids: frozenset[uuid.UUID] | None = None  # None = all departments
    station: str | None = None

    def can(self, permission: str) -> bool:
        return permission in self.permissions


SYSTEM = Actor(type="system", label="system")
GATEWAY = Actor(type="gateway", label="payment-gateway")

_request_meta: ContextVar[tuple[str | None, str | None]] = ContextVar("request_meta", default=(None, None))


def set_request_meta(ip: str | None, user_agent: str | None) -> None:
    _request_meta.set((ip, user_agent))


def request_meta() -> tuple[str | None, str | None]:
    return _request_meta.get()

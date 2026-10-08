"""Scheduled jobs. Each is a plain function that opens its own session — callable from Celery Beat,
from `python -m app.cli job <name>`, and directly from tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

JOBS: dict[str, Callable[[], Any]] = {}


def job(name: str) -> Callable[[Callable[[], Any]], Callable[[], Any]]:
    def deco(fn: Callable[[], Any]) -> Callable[[], Any]:
        JOBS[name] = fn
        return fn

    return deco


def load_all() -> None:
    """Import modules that register jobs."""
    import importlib

    for mod in (
        "app.modules.notifications.tasks",
        "app.modules.orders.tasks",
        "app.modules.payments.tasks",
        "app.modules.scheduling.tasks",
        "app.modules.analytics.tasks",
    ):
        try:
            importlib.import_module(mod)
        except ModuleNotFoundError:  # module not built yet
            continue


load_all()

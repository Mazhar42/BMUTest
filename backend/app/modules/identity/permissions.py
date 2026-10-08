"""Roles → permissions (ROADMAP §8). Permissions are plain strings checked by `require()`."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    HELP_DESK = "HELP_DESK"
    VERIFIER = "VERIFIER"
    BANK_TELLER = "BANK_TELLER"
    CASHIER = "CASHIER"
    COLLECTOR = "COLLECTOR"
    LAB_RECEPTION = "LAB_RECEPTION"
    TECHNICIAN = "TECHNICIAN"
    PATHOLOGIST = "PATHOLOGIST"
    REPORT_DESK = "REPORT_DESK"
    WAIVER_APPROVER = "WAIVER_APPROVER"
    LAB_ADMIN = "LAB_ADMIN"
    AUDITOR = "AUDITOR"
    SUPER_ADMIN = "SUPER_ADMIN"
    HOME_COLLECTOR = "HOME_COLLECTOR"


# Roles whose permissions are limited to their department's worklists.
DEPARTMENT_SCOPED = {Role.TECHNICIAN, Role.PATHOLOGIST}

# TOTP is mandatory for these roles (ROADMAP §6.4).
TOTP_REQUIRED = {Role.PATHOLOGIST, Role.LAB_ADMIN, Role.SUPER_ADMIN, Role.WAIVER_APPROVER}

# Only SUPER_ADMIN may grant these.
PRIVILEGED = {Role.LAB_ADMIN, Role.SUPER_ADMIN, Role.AUDITOR}

_COMMON = {"self.profile"}

ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.HELP_DESK: {
        "patient.search",
        "patient.register",
        "patient.view",
        "catalog.view",
        "order.create_walkin",
        "order.verify",
        "order.view",
        "order.cancel",
        "order.reprint_slip",
        "waiver.request",
        "queue.checkin",
        "home.manage",
    },
    Role.VERIFIER: {"patient.view", "catalog.view", "order.verify", "order.view", "prescription.view"},
    Role.BANK_TELLER: {"payment.teller.receive", "order.lookup", "queue.token.print"},
    Role.CASHIER: {
        "payment.counter.receive",
        "order.lookup",
        "queue.token.print",
        "payment.view",
        "payment.refund.request",
    },
    Role.COLLECTOR: {"queue.checkin", "queue.call", "specimen.collect", "order.view", "order.lookup", "patient.view"},
    Role.LAB_RECEPTION: {"specimen.receive", "specimen.reject", "order.lookup"},
    Role.TECHNICIAN: {"result.enter", "worklist.view", "order.lookup", "analyzer.view"},
    Role.PATHOLOGIST: {
        "result.enter",
        "result.verify",
        "report.release",
        "report.amend",
        "worklist.view",
        "order.lookup",
        "report.view",
        "analyzer.view",
    },
    Role.REPORT_DESK: {"report.deliver", "report.view", "order.lookup", "patient.view"},
    Role.WAIVER_APPROVER: {"waiver.approve", "order.view", "order.lookup", "patient.view"},
    Role.LAB_ADMIN: {
        "catalog.view",
        "catalog.manage",
        "capacity.manage",
        "staff.manage",
        "settings.manage",
        "downtime.manage",
        "device.manage",
        "backentry.create",
        "payment.view",
        "payment.reconcile",
        "payment.refund.approve",
        "payment.refund.request",
        "analytics.view",
        "order.view",
        "order.lookup",
        "order.cancel",
        "patient.view",
        "patient.search",
        "report.revoke",
        "report.view",
        "queue.call",
        "queue.checkin",
        "fhir.export",
        "home.manage",
        "worklist.view",
    },
    Role.AUDITOR: {"audit.view", "analytics.view", "order.view", "order.lookup", "payment.view"},
    Role.HOME_COLLECTOR: {"home.collect", "specimen.collect", "order.lookup"},
    Role.SUPER_ADMIN: set(),  # filled below: everything
}

ALL_PERMISSIONS: set[str] = set().union(*ROLE_PERMISSIONS.values()) | {"admin.create", "audit.view"}
ROLE_PERMISSIONS[Role.SUPER_ADMIN] = set(ALL_PERMISSIONS)


def permissions_for(roles: set[Role]) -> frozenset[str]:
    perms: set[str] = set(_COMMON)
    for role in roles:
        perms |= ROLE_PERMISSIONS[role]
    return frozenset(perms)

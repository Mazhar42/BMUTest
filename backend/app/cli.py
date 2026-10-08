"""Admin CLI: `python -m app.cli <command>`.

create-superadmin [--username U --full-name N --password P]   (prompts when omitted)
openapi                                                        print the OpenAPI JSON
seed [--demo]                                                  import placeholder catalog (+ demo data)
backup                                                         pg_dump + object-store mirror (M9)
job <name>                                                     run a scheduled job once
"""

from __future__ import annotations

import argparse
import getpass
import importlib
import json
import sys

from app.db import session_factory


def _create_superadmin(args: argparse.Namespace) -> int:
    from app.modules.identity import service

    username = args.username or input("username: ").strip().lower()
    full_name = args.full_name or input("full name: ").strip()
    password = args.password or getpass.getpass("password (min 10 chars): ")
    if len(password) < 10:
        print("password too short", file=sys.stderr)
        return 2
    with session_factory()() as db:
        staff = service.create_superadmin(db, username, full_name, password)
        db.commit()
        print(f"created SUPER_ADMIN {staff.username} ({staff.id}). TOTP enrolment happens at first login.")
    return 0


def _openapi(_: argparse.Namespace) -> int:
    from app.main import app

    sys.stdout.write(json.dumps(app.openapi(), ensure_ascii=False, indent=1))
    return 0


def _seed(args: argparse.Namespace) -> int:
    from app.seeding import run_seed

    with session_factory()() as db:
        summary = run_seed(db, demo=args.demo)
        db.commit()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _backup(_: argparse.Namespace) -> int:
    try:
        backup = importlib.import_module("app.ops.backup")
    except ModuleNotFoundError:
        print("backup is built in M9 (docs/ROADMAP.md); use deploy/backup.sh meanwhile", file=sys.stderr)
        return 2
    print(json.dumps(backup.run_backup(), indent=2))
    return 0


def _job(args: argparse.Namespace) -> int:
    from app.workers.jobs import JOBS

    fn = JOBS.get(args.name)
    if fn is None:
        print(f"unknown job; choose from: {', '.join(sorted(JOBS))}", file=sys.stderr)
        return 2
    print(json.dumps(fn(), default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-superadmin")
    p.add_argument("--username")
    p.add_argument("--full-name")
    p.add_argument("--password")
    p.set_defaults(fn=_create_superadmin)
    sub.add_parser("openapi").set_defaults(fn=_openapi)
    p = sub.add_parser("seed")
    p.add_argument("--demo", action="store_true", help="also create demo staff, patients and capacity")
    p.set_defaults(fn=_seed)
    sub.add_parser("backup").set_defaults(fn=_backup)
    p = sub.add_parser("job")
    p.add_argument("name")
    p.set_defaults(fn=_job)
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())

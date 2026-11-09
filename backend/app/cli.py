"""Command-line tools (run inside the backend container):

  python -m app.cli seed [--if-empty]            starter content for an empty database
  python -m app.cli create-admin --email ...     first (or another) staff account
  python -m app.cli reset-password --email ...   new password; also unlocks and signs out everywhere

Passwords are asked for on the keyboard (never as an argument, which shell history would keep).
For scripts, set the ADMIN_PASSWORD environment variable instead.
"""

import argparse
import getpass
import os
import re
import sys

from sqlalchemy import select

from app.core import security
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import User
from app.models.enums import Role
from app.seed.loader import is_empty, load_seed
from app.services import audit
from app.services.auth import revoke_all_sessions

_EMAIL = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


def seed(*, if_empty: bool) -> int:
    settings = get_settings()
    with SessionLocal() as db:
        if not is_empty(db):
            if if_empty:
                print("Starter content: skipped (the database already has content).")
                return 0
            print("The database already has content; nothing was added.", file=sys.stderr)
            return 1
        counts = load_seed(db, settings.upload_dir)
        db.commit()
    print("Starter content added:", ", ".join(f"{n} {what}" for what, n in counts.items()))
    return 0


def _ask_password(email: str, name: str) -> str | None:
    password = os.environ.get("ADMIN_PASSWORD") or ""
    if not password:
        password = getpass.getpass("Password (at least 12 characters): ")
        if getpass.getpass("Repeat the password: ") != password:
            print("The two passwords are different.", file=sys.stderr)
            return None
    problem = security.check_password_strength(password, email=email, name=name)
    if problem:
        print(problem, file=sys.stderr)
        return None
    return password


def create_admin(*, email: str, name: str, role: str) -> int:
    email = email.strip().lower()
    if not _EMAIL.match(email) or len(email) > 254:
        print("That e-mail address is not valid.", file=sys.stderr)
        return 1
    if not 1 <= len(name.strip()) <= 80:
        print("The name must be 1 to 80 characters.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print("An account with that e-mail already exists.", file=sys.stderr)
            return 1
        password = _ask_password(email, name)
        if password is None:
            return 1
        user = User(
            email=email,
            name=name.strip(),
            password_hash=security.hash_password(password),
            role=role,
        )
        db.add(user)
        db.flush()
        audit.record(db, "user_created_cli", user_id=user.id, entity="user", entity_id=user.id)
        db.commit()
    print(f"Created {role} {email}.")
    if role == Role.SUPER_ADMIN:
        print("Sign in, then turn on two-factor login (required for super admins).")
    return 0


def reset_password(*, email: str) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            print("No account with that e-mail.", file=sys.stderr)
            return 1
        password = _ask_password(user.email, user.name)
        if password is None:
            return 1
        user.password_hash = security.hash_password(password)
        user.failed_logins = 0
        user.locked_until = None
        revoke_all_sessions(db, user.id)
        audit.record(db, "password_reset_cli", user_id=user.id, entity="user", entity_id=user.id)
        db.commit()
    print("Password changed. The account is unlocked and signed out everywhere.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    seed_parser = commands.add_parser("seed", help="add the starter content to an empty database")
    seed_parser.add_argument(
        "--if-empty", action="store_true", help="do nothing (and succeed) if content already exists"
    )

    admin_parser = commands.add_parser("create-admin", help="create a staff account")
    admin_parser.add_argument("--email", required=True)
    admin_parser.add_argument("--name", required=True)
    admin_parser.add_argument(
        "--role", choices=[r.value for r in Role], default=Role.SUPER_ADMIN.value
    )

    reset_parser = commands.add_parser("reset-password", help="set a new password for an account")
    reset_parser.add_argument("--email", required=True)

    args = parser.parse_args()
    if args.command == "seed":
        return seed(if_empty=args.if_empty)
    if args.command == "create-admin":
        return create_admin(email=args.email, name=args.name, role=args.role)
    return reset_password(email=args.email)


if __name__ == "__main__":
    sys.exit(main())

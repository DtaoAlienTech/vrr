"""Command-line tools:  python -m app.cli seed [--if-empty]"""

import argparse
import sys

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.seed.loader import is_empty, load_seed


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    seed_parser = commands.add_parser("seed", help="add the starter content to an empty database")
    seed_parser.add_argument(
        "--if-empty", action="store_true", help="do nothing (and succeed) if content already exists"
    )
    args = parser.parse_args()
    return seed(if_empty=args.if_empty)


if __name__ == "__main__":
    sys.exit(main())

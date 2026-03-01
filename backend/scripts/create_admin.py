#!/usr/bin/env python3
"""Create or reset the default admin account.

Usage:
    python scripts/create_admin.py
    python scripts/create_admin.py --password mypass
    python scripts/create_admin.py --username admin --password secret --db-path /tmp/estimation.db
"""

import argparse
import sys
from pathlib import Path

# Ensure backend/src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(description="Create or reset the admin account")
    parser.add_argument("--username", default="admin", help="Admin username (default: admin)")
    parser.add_argument("--password", default="admin", help="Admin password (default: admin)")
    parser.add_argument("--db-path", default=None, help="Path to SQLite database file")
    args = parser.parse_args()

    # Ensure schema and tables exist
    from src.database.migrations import init_database
    init_database(db_path=args.db_path)

    from src.database.engine import get_engine
    engine = get_engine(db_path=args.db_path)

    import bcrypt
    from src.auth.models import User

    password_hash = bcrypt.hashpw(args.password.encode(), bcrypt.gensalt()).decode()

    with Session(engine) as session:
        existing = session.query(User).filter(User.username == args.username).first()

        if existing:
            existing.password_hash = password_hash
            existing.role = "ADMIN"
            existing.is_active = True
            session.commit()
            print(f"Admin account reset. Username: {args.username}, Password: {args.password}")
        else:
            admin = User(
                username=args.username,
                display_name="Administrator",
                email=f"{args.username}@localhost",
                password_hash=password_hash,
                auth_provider="local",
                role="ADMIN",
                is_active=True,
            )
            session.add(admin)
            session.commit()
            print(f"Admin account created. Username: {args.username}, Password: {args.password}")


if __name__ == "__main__":
    main()

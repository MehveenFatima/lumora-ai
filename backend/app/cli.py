"""
Operational commands for LumoraAI. Run from the repository root:

    python -m backend.app.cli migrate
    python -m backend.app.cli create-user --email you@example.com --name "Your Name"
    python -m backend.app.cli claim-workspaces --email you@example.com

`migrate` applies backend/app/db/migrations/*.sql in order and records each file in
`schema_migrations`, so it is safe to run on every deploy.
"""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path

from backend.app.core.config import settings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "db" / "migrations"


async def _connect():
    if not settings.database_url:
        sys.exit("DATABASE_URL is not set.")
    import asyncpg

    return await asyncpg.connect(settings.database_url)


async def migrate() -> None:
    conn = await _connect()
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        applied = {r["filename"] for r in await conn.fetch("SELECT filename FROM schema_migrations")}
        files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
        pending = [f for f in files if f.name not in applied]
        for f in pending:
            print(f"Applying {f.name} ...")
            async with conn.transaction():
                await conn.execute(f.read_text(encoding="utf-8"))
                await conn.execute("INSERT INTO schema_migrations (filename) VALUES ($1)", f.name)
        print(f"Database is up to date ({len(files)} migrations, {len(pending)} applied now).")
    finally:
        await conn.close()


async def create_user(email: str, name: str, password: str) -> None:
    from backend.app.core.security import hash_password
    from backend.app.repositories.users import EmailAlreadyRegisteredError, user_repo

    try:
        user = await user_repo.create(email=email, name=name, password_hash=hash_password(password))
    except EmailAlreadyRegisteredError:
        sys.exit(f"An account with email {email} already exists.")
    print(f"Created user {user['email']} ({user['id']}).")


async def claim_workspaces(email: str) -> None:
    from backend.app.repositories.users import user_repo
    from backend.app.repositories.workspaces import workspace_repo

    user = await user_repo.get_by_email(email)
    if not user:
        sys.exit(f"No account found for {email}. Register in the app or run create-user first.")
    count = await workspace_repo.claim_unowned(user["id"])
    print(f"Assigned {count} unowned workspace(s) to {user['email']}.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m backend.app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="Apply pending SQL migrations")

    cu = sub.add_parser("create-user", help="Create an account")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--password", help="Prompted for if omitted")

    cw = sub.add_parser("claim-workspaces", help="Give workspaces without an owner to an account")
    cw.add_argument("--email", required=True)

    args = parser.parse_args()
    if args.command == "migrate":
        asyncio.run(migrate())
    elif args.command == "create-user":
        password = args.password or getpass.getpass("Password: ")
        if len(password) < 8:
            sys.exit("Password must be at least 8 characters.")
        asyncio.run(create_user(args.email, args.name, password))
    elif args.command == "claim-workspaces":
        asyncio.run(claim_workspaces(args.email))


if __name__ == "__main__":
    main()

"""
Applies backend/app/db/migrations/*.sql in order and records each file in `schema_migrations`.

Used by `python -m backend.app.cli migrate` and by the API itself once it reaches the database,
so a deploy never depends on the database being reachable at the exact moment the container starts.
"""
import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
# Any fixed number works; it only has to be the same for every instance of the API
MIGRATION_LOCK_ID = 7_314_202_611


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


async def apply_migrations(conn) -> tuple[int, list[str]]:
    """Returns (number of migration files, names applied now). Safe to run on every start."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    applied = {r["filename"] for r in await conn.fetch("SELECT filename FROM schema_migrations")}
    files = migration_files()
    done = []
    for f in files:
        if f.name in applied:
            continue
        async with conn.transaction():
            # Two instances starting together must not apply the same file twice. A transaction-level
            # lock also works through a connection pooler, unlike a session-level one.
            await conn.execute("SELECT pg_advisory_xact_lock($1)", MIGRATION_LOCK_ID)
            if await conn.fetchval("SELECT 1 FROM schema_migrations WHERE filename = $1", f.name):
                continue
            await conn.execute(f.read_text(encoding="utf-8"))
            await conn.execute("INSERT INTO schema_migrations (filename) VALUES ($1)", f.name)
        done.append(f.name)
    return len(files), done


def _masked(message: str) -> str:
    """First line of an unrecognised error, with user names and hosts masked."""
    first = message.strip().splitlines()[0] if message.strip() else ""
    first = re.sub(r"postgres\.[A-Za-z0-9]+", "postgres.***", first)
    first = re.sub(r"[A-Za-z0-9-]+\.(supabase|pooler\.supabase)\.(co|com)", "***.supabase", first)
    first = re.sub(r"(user|role|database)\s+\"[^\"]*\"", r'\1 "***"', first)
    return first[:100]


def describe_db_error(e: BaseException) -> str:
    """A short, secret-free reason a database connection failed, for logs and the health check."""
    text = str(e).lower()
    # Supabase's pooler words a paused or deleted project in several ways
    if ("tenant or user not found" in text or "tenant/user" in text or "enotfound" in text
            or "project is paused" in text or "tenant not found" in text):
        return "project_not_found_or_paused"
    if "circuit breaker" in text or "edbhandlerexited" in text or "database is starting" in text:
        return "database_starting_or_restoring"
    if "max client connections" in text or "max_client_conn" in text or "remaining connection slots" in text:
        return "too_many_connections"
    if "password authentication failed" in text:
        return "authentication_failed"
    if "too many" in text and "connection" in text:
        return "too_many_connections"
    if "ssl" in text and ("required" in text or "refused" in text):
        return "ssl_required"
    if "does not exist" in text and "database" in text:
        return "database_missing"
    name = type(e).__name__
    if name in ("gaierror",) or "name or service not known" in text or "nodename nor servname" in text:
        return "host_not_found"
    if isinstance(e, ConnectionRefusedError) or "connection refused" in text:
        return "connection_refused"
    if "timeout" in name.lower() or "timed out" in text:
        return "timeout"
    detail = _masked(str(e))
    return f"{name}: {detail}" if detail else name

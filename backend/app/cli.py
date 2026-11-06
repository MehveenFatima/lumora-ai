"""
Operational commands for LumoraAI. Run from the repository root:

    python -m backend.app.cli migrate
    python -m backend.app.cli create-user --email you@example.com --name "Your Name"
    python -m backend.app.cli claim-workspaces --email you@example.com
    python -m backend.app.cli preview-study-material notes.pdf --out preview.md

`migrate` applies backend/app/db/migrations/*.sql in order and records each file in
`schema_migrations`, so it is safe to run on every deploy.
"""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path

from backend.app.core.config import settings


async def _connect():
    if not settings.database_url:
        sys.exit("DATABASE_URL is not set.")
    import asyncpg

    # The database may still be starting (e.g. in Docker Compose or right after a deploy)
    for attempt in range(1, 7):
        try:
            return await asyncpg.connect(settings.database_url, timeout=30)
        except (OSError, asyncpg.PostgresError, asyncio.TimeoutError) as e:
            if attempt == 6:
                from backend.app.db.migrations_runner import describe_db_error

                sys.exit(f"Could not connect to the database: {describe_db_error(e)}")
            delay = 2 ** (attempt - 1)
            print(f"Database not reachable yet ({type(e).__name__}); retrying in {delay}s ...")
            await asyncio.sleep(delay)


async def migrate() -> None:
    from backend.app.db.migrations_runner import apply_migrations

    conn = await _connect()
    try:
        total, done = await apply_migrations(conn)
        for name in done:
            print(f"Applied {name}")
        print(f"Database is up to date ({total} migrations, {len(done)} applied now).")
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


async def preview_study_material(path: str, out: str, max_concepts: int) -> None:
    """Runs the topic map, quiz and flashcard pipeline on one file and writes a Markdown report.

    Nothing is stored. Needs GEMINI_API_KEY; use it to judge question quality on your own notes.
    """
    from backend.app.ai.gateway import ai_gateway
    from backend.app.ai.types import TaskType
    from backend.app.services import flashcard_builder
    from backend.app.services.chunker import chunker_service
    from backend.app.services.concept_map import concept_map_service
    from backend.app.services.document_parser import document_parser
    from backend.app.services.question_bank import generate_for_concept
    from backend.app.services.similarity import DuplicateIndex

    if not ai_gateway.has_configured_provider(TaskType.QUIZ):
        sys.exit("Set GEMINI_API_KEY (or a secondary provider key) to preview AI-written study material.")
    file = Path(path)
    if not file.is_file():
        sys.exit(f"File not found: {path}")
    pages = document_parser.parse(file.read_bytes(), file.suffix.lstrip(".").lower())
    chunks = [
        {**c.to_dict(), "document_name": file.name}
        for c in chunker_service.chunk_pages("preview", "preview_doc", pages, file.stem, file.name)
    ]
    print(f"{len(pages)} pages, {len(chunks)} chunks. Building the topic map ...")
    concepts = await concept_map_service.extract(chunks, file.name)
    concepts = [{**c, "id": f"c{i}", "document_id": "preview_doc", "document_name": file.name} for i, c in enumerate(concepts)]
    print(f"{len(concepts)} concepts. Writing questions and flashcards ...")

    lines = [f"# Study material preview: {file.name}", "", f"{len(concepts)} concepts", ""]
    duplicates = DuplicateIndex()
    for c in concepts[:max_concepts]:
        source = concept_map_service.source_text(c, chunks)
        questions = await generate_for_concept(c, source, 6, duplicates)
        lines += [f"## {c['concept']}  ({c['topic']}, pages {c['source_pages']})", "", c.get("summary", ""), ""]
        lines += [f"- {p}" for p in c.get("key_points") or []] + ["", f"### Questions ({len(questions)} kept)", ""]
        for q in questions:
            lines.append(f"**[{q.difficulty}, {q.question_type}]** {q.question_text}")
            lines += [f"- {'**' if o['key'] == q.correct_option else ''}{o['key']}. {o['text']}{'**' if o['key'] == q.correct_option else ''}" for o in q.options]
            lines += [f"  _{q.explanation}_", ""]
        print(f"  {c['concept']}: {len(questions)} questions")
    cards = await flashcard_builder.write_cards(concepts[:max_concepts], chunks)
    lines += ["## Flashcards", ""]
    for card in cards:
        lines += [f"- **{card['front']}** {card['back']}  _({card['concept']})_"]
    Path(out).write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(cards)} flashcards. Report written to {out}")


async def fit_bkt() -> None:
    import json

    conn = await _connect()  # waits for the database, then the app's pool is used
    await conn.close()
    from backend.app.db.connection import close_db_pool
    from backend.app.services import bkt_fitting

    try:
        result = await bkt_fitting.refit()
        print(json.dumps(result, indent=2, default=str))
    finally:
        await close_db_pool()


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

    ps = sub.add_parser("preview-study-material", help="Preview the topic map, quiz questions and flashcards for a file")
    ps.add_argument("file")
    ps.add_argument("--out", default="study-material-preview.md")
    ps.add_argument("--max-concepts", type=int, default=12)

    sub.add_parser("fit-bkt", help="Fit the BKT parameters from the quiz answers collected so far")

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
    elif args.command == "fit-bkt":
        asyncio.run(fit_bkt())
    elif args.command == "preview-study-material":
        asyncio.run(preview_study_material(args.file, args.out, args.max_concepts))


if __name__ == "__main__":
    main()

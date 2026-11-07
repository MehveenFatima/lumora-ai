"""
Built-in sample workspaces: Operating Systems, DBMS and Computer Networks.

Each one is created for the signed-in user from notes that ship with the app
(`sample_content/pdfs`). The PDF goes through the normal upload pipeline (parsing, chunking,
embeddings) in the background, so the tutor and search work on it like on any upload. The topic map, the question
bank and the flashcard deck are written from the same notes and stored ready to use, so quizzes,
flashcards, mastery tracking, knowledge gaps, analytics and the study plan all work straight away
without waiting for an AI provider. Sample workspaces are flagged `is_sample`, look like any other
workspace to the user, and their material is not regenerated in the background.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

from backend.app.core.logging import get_logger
from backend.app.repositories.concepts import concept_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.secondary import flashcard_repo
from backend.app.repositories.workspaces import workspace_repo
from backend.app.sample_content import cn, dbms, os as os_notes
from backend.app.services import question_bank as qb

logger = get_logger(__name__)

MODULES = [os_notes, dbms, cn]
PDF_DIR = Path(__file__).resolve().parent.parent / "sample_content" / "pdfs"
TARGET_DAYS = 14
DAILY_MINUTES = 45
SAMPLE_GENERATOR = qb.GENERATOR_TAG  # same tag as generated material, so every feature reads it


async def _existing_sample_names(owner_id: str) -> set:
    return {
        (w.get("name") or "").strip().lower()
        for w in await workspace_repo.list_by_owner(owner_id)
        if w.get("is_sample")
    }


async def _create_document(workspace_id: str, filename: str) -> Dict[str, Any]:
    data = (PDF_DIR / filename).read_bytes()
    title = filename.rsplit(".", 1)[0].replace("_", " ")
    return await document_repo.create(
        workspace_id=workspace_id, title=title, filename=filename, file_type="pdf",
        file_size=len(data), status="processing",
    )


async def _index_documents(docs: List[Dict[str, Any]]) -> None:
    """Indexes the notes (parse, chunk, embed) one after another, after the response has gone
    out. The quizzes, flashcards and plan don't wait for this; the tutor's search does."""
    from backend.app.api.routes.documents import _ingest_document

    for doc in docs:
        filename = doc["filename"]
        try:
            await _ingest_document(
                {"background": True, "offline_fallback": True},
                str(doc["workspace_id"]), str(doc["id"]), doc["title"], filename, "pdf",
                (PDF_DIR / filename).read_bytes(), "application/pdf",
            )
        except Exception:
            logger.error(f"Indexing the notes '{filename}' failed", exc_info=True)


def _start_indexing(docs: List[Dict[str, Any]]) -> None:
    from backend.app.api.routes.documents import _INGEST_TASKS

    task = asyncio.create_task(_index_documents(docs))
    _INGEST_TASKS.add(task)
    task.add_done_callback(_INGEST_TASKS.discard)


async def _store_material(workspace_id: str, doc: Dict[str, Any], module) -> Dict[str, int]:
    doc_id = str(doc["id"])
    doc_name = module.WORKSPACE["pdf"]
    saved = await concept_repo.replace_for_document(
        workspace_id, doc_id, doc_name,
        [
            {
                "topic": c["topic"], "concept": c["concept"], "summary": c["summary"],
                "key_points": c["key_points"], "source_pages": [c["page"]],
            }
            for c in module.CONCEPTS
        ],
        method="sample",
    )
    ids = {s["concept"]: s["id"] for s in saved}

    questions = []
    cards: List[Dict[str, Any]] = []
    for c in module.CONCEPTS:
        concept = {
            "topic": c["topic"], "concept": c["concept"], "source_pages": [c["page"]],
            "document_id": doc_id, "document_name": doc_name,
        }
        for difficulty, text, options, answer, explanation in c["questions"]:
            q = qb.build_question(
                {
                    "question_text": text, "options": options, "correct_option": answer,
                    "explanation": explanation, "difficulty": difficulty, "source_page": c["page"],
                },
                concept,
                source_excerpt=c["summary"],
            )
            if q is None:
                logger.warning(f"Sample question rejected by the validator: {text}")
                continue
            q.concept_id = ids.get(c["concept"])
            questions.append(q)
        for front, back in c["cards"]:
            cards.append({
                "front": front, "back": back, "concept": c["concept"], "concept_id": ids.get(c["concept"]),
                "document_id": doc_id, "source_document": doc_name, "source_page": c["page"],
                "generator": SAMPLE_GENERATOR,
            })

    stored_q = await qb.store_questions(workspace_id, questions)
    stored_c = await flashcard_repo.save_flashcards(workspace_id, cards)
    return {"concepts": len(saved), "questions": stored_q, "flashcards": len(stored_c)}


async def create_for_user(owner_id: str, wait_for_indexing: bool = False) -> List[Dict[str, Any]]:
    """Creates the sample workspaces the user doesn't have yet. Returns the created workspaces."""
    have = await _existing_sample_names(owner_id)
    created = []
    docs: List[Dict[str, Any]] = []
    for module in MODULES:
        spec = module.WORKSPACE
        if spec["name"].lower() in have:
            continue
        ws_id = f"ws_{uuid.uuid4().hex[:14]}"
        await workspace_repo.create(
            workspace_id=ws_id,
            name=spec["name"],
            goal=spec["goal"],
            level=spec["level"],
            target_date=(date.today() + timedelta(days=TARGET_DAYS)).isoformat(),
            daily_target_minutes=DAILY_MINUTES,
            description=f"Exam revision for {spec['name']} from the course notes",
            owner_id=owner_id,
        )
        # Flag first, so the background preparation started by the upload leaves it alone
        await workspace_repo.mark_sample(ws_id)
        try:
            doc = await _create_document(ws_id, spec["pdf"])
            counts = await _store_material(ws_id, doc, module)
            docs.append(doc)
        except Exception:
            logger.error(f"Could not create the sample workspace '{spec['name']}'", exc_info=True)
            await workspace_repo.delete(ws_id)
            raise
        logger.info(f"Sample workspace '{spec['name']}' created for {owner_id}: {counts}")
        created.append(await workspace_repo.get_by_id(ws_id))
    if docs:
        if wait_for_indexing:
            await _index_documents(docs)
        else:
            _start_indexing(docs)
    return created

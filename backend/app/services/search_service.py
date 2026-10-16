"""
Workspace search behind the header search box (Ctrl/Cmd + K).

Matches the query against topic names, documents, flashcards and the text of the indexed notes,
and returns typed results with a link to the page that shows each one.
"""
import re
from typing import Any, Dict, List
from urllib.parse import quote

from backend.app.core.logging import get_logger
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.secondary import flashcard_repo
from backend.app.services.text_cleanup import clean_study_text

logger = get_logger(__name__)

MAX_PER_GROUP = 5


def _snippet(text: str, terms: List[str], width: int = 160) -> str:
    text = clean_study_text(text)
    lower = text.lower()
    hit = min((lower.find(t) for t in terms if lower.find(t) >= 0), default=0)
    start = max(0, hit - width // 3)
    end = min(len(text), start + width)
    cut = text[start:end].strip()
    if start > 0:
        cut = "…" + cut.split(" ", 1)[-1]
    if end < len(text):
        cut = cut.rsplit(" ", 1)[0] + "…"
    return cut


def _score(haystack: str, query: str, terms: List[str]) -> float:
    h = (haystack or "").lower()
    if not h:
        return 0.0
    score = 3.0 if query in h else 0.0
    if h.startswith(query):
        score += 2.0
    score += sum(1.0 for t in terms if t in h)
    return score


class SearchService:
    async def search(self, workspace_id: str, query: str) -> Dict[str, Any]:
        q = re.sub(r"\s+", " ", (query or "").strip().lower())[:100]
        terms = [t for t in re.findall(r"[a-z0-9][a-z0-9+#./-]*", q) if len(t) >= 2]
        if len(q) < 2 or not terms:
            return {"query": query, "results": []}
        base = f"/dashboard/workspace/{workspace_id}"
        results: List[Dict[str, Any]] = []

        # Topics: the concept inventory that drives quizzes and the Topics page
        try:
            from backend.app.services.question_generator import question_generator_service

            concepts = await question_generator_service.extract_available_concepts(workspace_id)
            scored = sorted(
                ((_score(c["concept"], q, terms), c) for c in concepts), key=lambda x: x[0], reverse=True
            )
            for score, c in scored[:MAX_PER_GROUP]:
                if score <= 0:
                    break
                results.append({
                    "type": "topic",
                    "title": c["concept"],
                    "snippet": f"Topic in {c.get('topic') or 'your notes'}",
                    "link": f"{base}/topics?topic={quote(c['concept'])}",
                    "score": score + 1,
                })
        except Exception as e:  # a workspace without documents has no concepts yet
            logger.debug(f"Topic search skipped: {e}")

        # Documents
        for d in await document_repo.list_by_workspace(workspace_id):
            score = max(_score(d.get("title", ""), q, terms), _score(d.get("filename", ""), q, terms))
            if score > 0:
                results.append({
                    "type": "document",
                    "title": d.get("title") or d.get("filename"),
                    "snippet": f"{d.get('page_count') or 0} pages · {d.get('status')}",
                    "link": f"{base}/sources",
                    "score": score,
                })

        # Flashcards
        cards = []
        for c in await flashcard_repo.list_by_workspace(workspace_id):
            score = _score(f"{c.get('front', '')} {c.get('concept', '')}", q, terms) * 1.2 + _score(c.get("back", ""), q, terms) * 0.5
            if score > 0:
                cards.append((score, c))
        for score, c in sorted(cards, key=lambda x: x[0], reverse=True)[:MAX_PER_GROUP]:
            results.append({
                "type": "flashcard",
                "title": c.get("front"),
                "snippet": _snippet(c.get("back", ""), terms, 120),
                "link": f"{base}/flashcards",
                "score": score,
            })

        # Passages from the notes, with page numbers
        try:
            chunks = await chunk_repo.search_lexical_chunks(workspace_id, terms, top_k=MAX_PER_GROUP)
        except Exception as e:
            logger.warning(f"Passage search failed: {e}")
            chunks = []
        for ch in chunks:
            text = ch.get("text") or ""
            score = _score(text, q, terms)
            if score <= 0:
                continue
            results.append({
                "type": "passage",
                "title": clean_study_text(ch.get("heading") or "") or (ch.get("document_name") or "Notes"),
                "snippet": _snippet(text, terms),
                "link": f"{base}/tutor?ask={quote(query.strip()[:100])}",
                "meta": f"{ch.get('document_name') or 'Document'} · page {ch.get('page_number') or 1}",
                "score": score * 0.8,
            })

        order = {"topic": 0, "document": 1, "flashcard": 2, "passage": 3}
        results.sort(key=lambda r: (order[r["type"]], -r["score"]))
        for r in results:
            r.pop("score", None)
        return {"query": query, "results": results}


search_service = SearchService()

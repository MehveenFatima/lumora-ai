"""
Cleanup helpers for text extracted from study material.

PDF extraction keeps layout artefacts that read badly when shown back to a learner: running
headers, card and question numbers ("Card 1 front", "Q1 Q2 Q5"), bullet glyphs, page labels.
These helpers strip that noise and cut text at sentence or word boundaries.
"""
import re
from typing import Optional

# "Card 1 front", "Card 12 back"
_CARD_LABEL = re.compile(r"\bCard\s*\d+\s*(?:front|back)\b", re.IGNORECASE)
# Runs of question numbers such as "Q1 Q2 Q5 Q9"
_QUESTION_NUMBER_RUN = re.compile(r"(?:\bQ\s?\d{1,3}[a-z]?\b[\s,·•|/]*){2,}", re.IGNORECASE)
# A single leading question number: "Q1 Steps to ...", "Q3) Define ..."
_QUESTION_NUMBER = re.compile(r"\bQ\s?\d{1,3}[a-z]?[\.\):]?\s+(?=[A-Za-z])", re.IGNORECASE)
_PAGE_LABEL = re.compile(r"\b(?:Page|Pg\.?)\s*\d+(?:\s*(?:of|/)\s*\d+)?\b", re.IGNORECASE)
_FILE_NAME = re.compile(r"\b[\w\-]+(?:\s*\(\d+\))?\.(?:pdf|docx?|pptx?|txt)\b", re.IGNORECASE)
_BULLETS = re.compile(r"\*+|(?:^|\s)[•▪◦●■►➢✓✔]+(?=\s)")
_SEPARATORS = re.compile(r"\s*[·•|]\s*")
_SPACES = re.compile(r"\s+")


def clean_study_text(text: Optional[str], heading: Optional[str] = None) -> str:
    """Removes layout noise from extracted text and collapses whitespace."""
    if not text:
        return ""
    cleaned = text.replace("\x00", " ")
    if heading:
        head = heading.strip()
        if head and cleaned.lstrip().startswith(head):
            cleaned = cleaned.lstrip()[len(head):]
    cleaned = _CARD_LABEL.sub(" ", cleaned)
    cleaned = _QUESTION_NUMBER_RUN.sub(" ", cleaned)
    cleaned = _QUESTION_NUMBER.sub("", cleaned)
    cleaned = _PAGE_LABEL.sub(" ", cleaned)
    cleaned = _FILE_NAME.sub(" ", cleaned)
    cleaned = _BULLETS.sub(" ", cleaned)
    cleaned = _SEPARATORS.sub(" ", cleaned)
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    return _SPACES.sub(" ", cleaned).strip(" -–:;,")


def clean_label(label: Optional[str]) -> Optional[str]:
    """Cleans a heading or concept name; returns None when nothing meaningful is left."""
    if not label:
        return None
    parts = [clean_study_text(p) for p in _SEPARATORS.split(label)]
    parts = [p for p in parts if len(p) >= 3 and re.search(r"[A-Za-z]{3,}", p)]
    if not parts:
        return None
    # Prefer the most specific segment, e.g. "MWT · EJB (Unit III)" -> "EJB (Unit III)"
    best = max(parts, key=lambda p: (len(re.findall(r"[A-Za-z]{3,}", p)), len(p))) if len(parts) > 1 else parts[0]
    best = best.strip()
    return best[:80] if len(best) >= 3 else None


def truncate_at_sentence(text: str, limit: int) -> str:
    """Shortens text to at most `limit` characters without cutting a word in half."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    window = text[:limit]
    sentence_end = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
    if window.endswith((".", "?", "!")):
        sentence_end = len(window) - 1
    if sentence_end >= limit * 0.5:
        return window[: sentence_end + 1].strip()
    word_end = window.rfind(" ")
    cut = window[:word_end] if word_end > 0 else window
    return cut.rstrip(" ,;:-–") + "…"


def split_sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]

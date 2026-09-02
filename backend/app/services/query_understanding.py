from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
import re
from backend.app.repositories.documents import document_repo
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ResolvedQuery:
    intent: str  # WORKSPACE_METADATA, DOCUMENT_SUMMARY, SPECIFIC_CONCEPT, PAGE_REFERENCE, PAGE_RANGE_REFERENCE, CONTEXTUAL_FOLLOWUP, DOCUMENT_TOPIC_QUERY, UNGROUNDED_QUERY, AMBIGUOUS_DOCUMENT
    target_document_id: Optional[str] = None
    target_document_name: Optional[str] = None
    target_document_page_count: Optional[int] = None
    page_number: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    resolved_concept: Optional[str] = None
    resolved_reference: Optional[str] = None
    semantic_query: str = ""
    candidate_documents: List[Dict[str, Any]] = field(default_factory=list)
    clarification_message: Optional[str] = None


class QueryUnderstandingService:
    def extract_concepts_from_history(
        self, recent_history: Optional[List[Dict[str, Any]]]
    ) -> Tuple[List[str], Optional[str], Optional[str]]:
        """
        Dynamically extracts structured concepts and the last referenced document
        from the most recent assistant response.
        """
        if not recent_history:
            return [], None, None

        last_assistant_msg = ""
        last_doc_id = None
        last_doc_name = None

        for msg in reversed(recent_history):
            if msg.get("role") == "assistant" and not last_assistant_msg:
                last_assistant_msg = msg.get("content", "")
                citations = msg.get("citations", [])
                if citations and isinstance(citations, list) and len(citations) > 0:
                    last_doc_id = str(citations[0].get("document_id"))
                    last_doc_name = citations[0].get("document_name")

        if not last_assistant_msg:
            return [], last_doc_id, last_doc_name

        concepts: List[str] = []

        # 1. Numbered items: "1. SSL Handshake Protocol: ..." or "1. **Ruby Object Model**"
        numbered = re.findall(
            r"(?:^|\n)\s*(?:\d+[\.\)]|\([0-9]+\))\s*(?:\*\*)?([^\n\:\-\*]+?)(?:\*\*)?(?:\:|\s*\-|\s*—|\n|$)",
            last_assistant_msg,
        )
        for c in numbered:
            clean_c = c.strip(" *#-_`").strip()
            if len(clean_c) >= 3 and clean_c.lower() not in [
                "core concept",
                "principles",
                "application",
                "step",
                "note",
                "summary",
                "overview",
                "conclusion",
            ]:
                concepts.append(clean_c)

        # 2. Bold concept headers: "**Concept Name**"
        if not concepts:
            bold_items = re.findall(r"\*\*([^\*\n]+?)\*\*", last_assistant_msg)
            for b in bold_items:
                clean_b = b.strip()
                if (
                    len(clean_b) >= 3
                    and len(clean_b.split()) <= 7
                    and not clean_b.lower().startswith("from ")
                    and not clean_b.lower().startswith("source")
                    and not clean_b.lower().startswith("based on")
                ):
                    concepts.append(clean_b)

        # 3. Bullet items: "- Concept: ..." or "* Concept: ..."
        if not concepts:
            bullets = re.findall(
                r"(?:^|\n)\s*[\-\*•]\s*([^\n\:\-]+?)(?:\:|\s*\-|\n|$)",
                last_assistant_msg,
            )
            for b in bullets:
                clean_b = b.strip(" *#-_`").strip()
                if len(clean_b) >= 3:
                    concepts.append(clean_b)

        return concepts, last_doc_id, last_doc_name

    def normalize_semantic_query(self, query: str, doc_name: Optional[str] = None) -> str:
        """
        Strips non-semantic boilerplate, filenames, and filler references from query text.
        """
        cleaned = query
        if doc_name:
            cleaned = re.sub(re.escape(doc_name), "", cleaned, flags=re.IGNORECASE)
            fn_no_ext = doc_name.rsplit(".", 1)[0] if "." in doc_name else doc_name
            cleaned = re.sub(re.escape(fn_no_ext), "", cleaned, flags=re.IGNORECASE)

        fillers = [
            r"\b(in this pdf|in this document|from this pdf|from this document|in the file|from the file)\b",
            r"\b(summarize it|explain it|describe it|tell me about)\b",
            r"\b(in this workspace|from this workspace)\b",
            r"\b(according to this document|based on this document)\b",
        ]
        for f in fillers:
            cleaned = re.sub(f, "", cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned if len(cleaned) >= 2 else query.strip()

    async def resolve_user_reference(
        self,
        workspace_id: str,
        user_message: str,
        recent_history: Optional[List[Dict[str, Any]]] = None,
        current_document_id: Optional[str] = None,
    ) -> ResolvedQuery:
        """
        Comprehensive query understanding, reference resolution, and intent classification.
        """
        q_raw = user_message.strip()
        q_lower = q_raw.lower()

        docs = await document_repo.list_by_workspace(workspace_id)
        doc_map = {str(d.get("id")): d for d in docs}

        # -------------------------------------------------------------
        # 1. WORKSPACE_METADATA INTENT
        # -------------------------------------------------------------
        metadata_patterns = [
            r"what (sources|documents|files|topics|materials) (are|do i have|exist|are indexed|are uploaded|are in this workspace|in this workspace)",
            r"how many (sources|documents|files|topics|pages) (are|do i have|exist|indexed|uploaded)",
            r"(show|list|tell) (me )?(all )?(available )?(sources|documents|files|topics|indexed)",
            r"what is (currently )?(indexed|in this workspace|uploaded)",
            r"which documents (are ready|do i have|are available)",
            r"what topics are (currently )?indexed",
            r"what files have i uploaded",
        ]
        if any(re.search(pat, q_lower) for pat in metadata_patterns):
            return ResolvedQuery(
                intent="WORKSPACE_METADATA",
                semantic_query=q_raw,
                candidate_documents=docs,
            )

        # -------------------------------------------------------------
        # 2. DOCUMENT RESOLUTION
        # -------------------------------------------------------------
        target_doc: Optional[Dict[str, Any]] = None

        # A. Explicit filename / title matching in query
        for d in docs:
            fn = d.get("filename", "").lower()
            title = d.get("title", "").lower()
            fn_no_ext = fn.rsplit(".", 1)[0] if "." in fn else fn

            if (
                fn in q_lower
                or fn_no_ext in q_lower
                or (len(fn_no_ext) >= 4 and fn_no_ext.split()[0] in q_lower)
                or (title and title in q_lower)
            ):
                target_doc = d
                break

        # B. Active current_document_id
        if not target_doc and current_document_id and current_document_id in doc_map:
            target_doc = doc_map[current_document_id]

        # C. If workspace has exactly 1 document, it is the sole active document
        if not target_doc and len(docs) == 1:
            target_doc = docs[0]

        # D. Conversation context inheritance
        history_concepts, last_doc_id, last_doc_name = self.extract_concepts_from_history(recent_history)
        if not target_doc and last_doc_id and last_doc_id in doc_map:
            target_doc = doc_map[last_doc_id]

        target_doc_id = str(target_doc["id"]) if target_doc else None
        target_doc_name = target_doc.get("filename") if target_doc else None
        target_doc_pages = target_doc.get("page_count") if target_doc else None

        # -------------------------------------------------------------
        # 3. PAGE RANGE REFERENCE INTENT (e.g. "pages 5 to 8", "pages 10-12")
        # -------------------------------------------------------------
        range_match = re.search(r"\bpages?\s+(\d+)\s*(?:to|\-|through|\.\.)\s*(\d+)\b", q_lower)
        if range_match:
            p_start = int(range_match.group(1))
            p_end = int(range_match.group(2))
            if p_start > p_end:
                p_start, p_end = p_end, p_start

            if not target_doc and len(docs) > 1:
                doc_list_text = "\n".join([f"{i+1}. {d.get('filename')}" for i, d in enumerate(docs)])
                return ResolvedQuery(
                    intent="AMBIGUOUS_DOCUMENT",
                    page_start=p_start,
                    page_end=p_end,
                    candidate_documents=docs,
                    clarification_message=f"Which document would you like me to explain pages {p_start} to {p_end} from? Your workspace contains:\n{doc_list_text}",
                )

            if target_doc and target_doc_pages and p_start > target_doc_pages:
                return ResolvedQuery(
                    intent="PAGE_RANGE_REFERENCE",
                    target_document_id=target_doc_id,
                    target_document_name=target_doc_name,
                    target_document_page_count=target_doc_pages,
                    page_start=p_start,
                    page_end=p_end,
                    clarification_message=f"Pages {p_start} to {p_end} do not exist in **{target_doc_name}**. The document contains {target_doc_pages} pages.",
                )

            return ResolvedQuery(
                intent="PAGE_RANGE_REFERENCE",
                target_document_id=target_doc_id,
                target_document_name=target_doc_name,
                target_document_page_count=target_doc_pages,
                page_start=p_start,
                page_end=p_end,
                semantic_query=f"Pages {p_start} to {p_end} summary",
            )

        # -------------------------------------------------------------
        # 4. SINGLE PAGE REFERENCE INTENT (e.g. "Explain page 7", "What does page 7 say?")
        # -------------------------------------------------------------
        page_match = re.search(r"\b(?:page|pg|page\s+number)\s+(\d+)\b", q_lower)
        if page_match:
            p_num = int(page_match.group(1))

            if not target_doc and len(docs) > 1:
                doc_list_text = "\n".join([f"{i+1}. {d.get('filename')}" for i, d in enumerate(docs)])
                return ResolvedQuery(
                    intent="AMBIGUOUS_DOCUMENT",
                    page_number=p_num,
                    candidate_documents=docs,
                    clarification_message=f"Which document would you like me to explain page {p_num} from? Your workspace contains:\n{doc_list_text}",
                )

            if target_doc and target_doc_pages and p_num > target_doc_pages:
                return ResolvedQuery(
                    intent="PAGE_REFERENCE",
                    target_document_id=target_doc_id,
                    target_document_name=target_doc_name,
                    target_document_page_count=target_doc_pages,
                    page_number=p_num,
                    clarification_message=f"Page {p_num} does not exist in **{target_doc_name}**. The document contains {target_doc_pages} pages.",
                )

            return ResolvedQuery(
                intent="PAGE_REFERENCE",
                target_document_id=target_doc_id,
                target_document_name=target_doc_name,
                target_document_page_count=target_doc_pages,
                page_number=p_num,
                semantic_query=f"Page {p_num} explanation",
            )

        # -------------------------------------------------------------
        # 5. CONTEXTUAL FOLLOW-UP INTENT
        # -------------------------------------------------------------
        followup_patterns = [
            r"\b(first|1st)\s+(concept|point|topic|item|algorithm|section|protocol|part)\b",
            r"\b(second|2nd)\s+(concept|point|topic|item|algorithm|section|protocol|part)\b",
            r"\b(third|3rd)\s+(concept|point|topic|item|algorithm|section|protocol|part)\b",
            r"\b(fourth|4th)\s+(concept|point|topic|item|algorithm|section|protocol|part)\b",
            r"\b(last)\s+(concept|point|topic|item|algorithm|section|protocol|part)\b",
            r"\bexplain\s+(the\s+)?(first|second|third|fourth|last)\b",
            r"\b(concrete\s+)?example\s+of\s+(that|this|it|the\s+first|the\s+second)\b",
            r"\b(explain|simplify|break\s+down)\s+(it|that|this)\b",
            r"\b(simpler|simple)\s+terms\b",
            r"\b(what\s+you\s+just\s+explained|we\s+just\s+discussed|you\s+just\s+mentioned)\b",
            r"\bexam\s+points\s+(from|about|on)\b",
            r"\bwhy\s+is\s+(that|this|it)\s+(important|used|needed)\b",
            r"\bhow\s+does\s+(that|this|it)\s+work\b",
        ]

        is_followup = bool(recent_history) and any(re.search(pat, q_lower) for pat in followup_patterns)

        if is_followup and history_concepts:
            # Ordinal resolution
            resolved_concept = None
            if re.search(r"\b(first|1st)\b", q_lower) and len(history_concepts) >= 1:
                resolved_concept = history_concepts[0]
            elif re.search(r"\b(second|2nd)\b", q_lower) and len(history_concepts) >= 2:
                resolved_concept = history_concepts[1]
            elif re.search(r"\b(third|3rd)\b", q_lower) and len(history_concepts) >= 3:
                resolved_concept = history_concepts[2]
            elif re.search(r"\b(fourth|4th)\b", q_lower) and len(history_concepts) >= 4:
                resolved_concept = history_concepts[3]
            elif re.search(r"\b(last)\b", q_lower):
                resolved_concept = history_concepts[-1]
            else:
                resolved_concept = history_concepts[0]

            # Formulate normalized semantic query without leaving "first concept" in text
            if "example" in q_lower:
                sem_q = f"Concrete example and practical mechanism of {resolved_concept}"
            elif "simpler" in q_lower or "simplify" in q_lower:
                sem_q = f"Fundamental principles and intuitive explanation of {resolved_concept}"
            elif "exam" in q_lower:
                sem_q = f"Important exam definitions and key concepts for {resolved_concept}"
            else:
                sem_q = f"Detailed explanation and technical architecture of {resolved_concept}"

            return ResolvedQuery(
                intent="CONTEXTUAL_FOLLOWUP",
                target_document_id=target_doc_id,
                target_document_name=target_doc_name,
                target_document_page_count=target_doc_pages,
                resolved_concept=resolved_concept,
                resolved_reference=resolved_concept,
                semantic_query=sem_q,
            )

        # -------------------------------------------------------------
        # 6. DOCUMENT TOPIC QUERY INTENT
        # -------------------------------------------------------------
        topic_patterns = [
            r"what are the (main |key |major )?topics in this document",
            r"what concepts are covered in this (pdf|document|file)",
            r"list the (major |main |key )?concepts in the (file|document|pdf)",
        ]
        if any(re.search(pat, q_lower) for pat in topic_patterns):
            if not target_doc and len(docs) > 1:
                doc_list_text = "\n".join([f"{i+1}. {d.get('filename')}" for i, d in enumerate(docs)])
                return ResolvedQuery(
                    intent="AMBIGUOUS_DOCUMENT",
                    candidate_documents=docs,
                    clarification_message=f"Which document would you like to explore topics for? Your workspace contains:\n{doc_list_text}",
                )

            return ResolvedQuery(
                intent="DOCUMENT_TOPIC_QUERY",
                target_document_id=target_doc_id,
                target_document_name=target_doc_name,
                target_document_page_count=target_doc_pages,
                semantic_query=f"Main topics and key concepts in {target_doc_name or 'document'}",
            )

        # -------------------------------------------------------------
        # 7. DOCUMENT SUMMARY INTENT
        # -------------------------------------------------------------
        summary_keywords = [
            "summar",
            "what are the concepts",
            "what concepts",
            "overview",
            "all concepts",
            "syllabus",
            "tell me about this",
            "explain this pdf",
            "what is this document about",
            "key points",
            "table of contents",
        ]
        is_summary = any(k in q_lower for k in summary_keywords) or (
            target_doc_name and ("summarize it" in q_lower or "summarize" in q_lower)
        )

        if is_summary:
            if not target_doc and len(docs) > 1:
                doc_list_text = "\n".join([f"{i+1}. {d.get('filename')}" for i, d in enumerate(docs)])
                return ResolvedQuery(
                    intent="AMBIGUOUS_DOCUMENT",
                    candidate_documents=docs,
                    clarification_message=f"Which document would you like me to summarize? Your workspace contains:\n{doc_list_text}",
                )

            return ResolvedQuery(
                intent="DOCUMENT_SUMMARY",
                target_document_id=target_doc_id,
                target_document_name=target_doc_name,
                target_document_page_count=target_doc_pages,
                semantic_query=f"Comprehensive summary and architecture of {target_doc_name or 'document'}",
            )

        # -------------------------------------------------------------
        # 8. SPECIFIC CONCEPT INTENT
        # -------------------------------------------------------------
        norm_query = self.normalize_semantic_query(q_raw, target_doc_name)
        return ResolvedQuery(
            intent="SPECIFIC_CONCEPT",
            target_document_id=target_doc_id,
            target_document_name=target_doc_name,
            target_document_page_count=target_doc_pages,
            semantic_query=norm_query,
        )


query_understanding_service = QueryUnderstandingService()

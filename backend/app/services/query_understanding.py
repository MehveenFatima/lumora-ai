import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from backend.app.repositories.documents import document_repo
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ResolvedQuery:
    intent: str  # WORKSPACE_METADATA, DOCUMENT_SUMMARY, SPECIFIC_CONCEPT, PAGE_REFERENCE, PAGE_RANGE_REFERENCE, CONTEXTUAL_FOLLOWUP, DOCUMENT_TOPIC_QUERY, COMPARE_CONTRAST, DIAGRAM_FIGURE_QUERY, TABLE_QUERY, AMBIGUOUS_DOCUMENT
    target_document_id: Optional[str] = None
    target_document_name: Optional[str] = None
    target_document_page_count: Optional[int] = None
    page_number: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    resolved_concept: Optional[str] = None
    resolved_concept_a: Optional[str] = None
    resolved_concept_b: Optional[str] = None
    resolved_reference: Optional[str] = None
    semantic_query: str = ""
    candidate_documents: List[Dict[str, Any]] = field(default_factory=list)
    clarification_message: Optional[str] = None
    is_visual_query: bool = False
    is_table_query: bool = False


class QueryUnderstandingService:
    def extract_concepts_from_history(
        self, recent_history: Optional[List[Dict[str, Any]]]
    ) -> Tuple[List[str], Optional[str], Optional[str]]:
        """
        Dynamically extracts structured concepts and the last referenced document
        from both the most recent assistant response and the last user prompt.
        """
        if not recent_history:
            return [], None, None

        last_assistant_msg = ""
        last_user_msg = ""
        last_doc_id = None
        last_doc_name = None

        for msg in reversed(recent_history):
            role = msg.get("role")
            if role == "assistant" and not last_assistant_msg:
                last_assistant_msg = msg.get("content", "")
                citations = msg.get("citations", [])
                if citations and isinstance(citations, list) and len(citations) > 0:
                    last_doc_id = str(citations[0].get("document_id"))
                    last_doc_name = citations[0].get("document_name")
            elif role == "user" and not last_user_msg:
                last_user_msg = msg.get("content", "")

        concepts: List[str] = []

        # 1. Numbered items in assistant response: "1. SSL Handshake Protocol: ..." or "> 1. SSL Handshake Protocol:"
        if last_assistant_msg:
            numbered = re.findall(
                r"(?:^|\n)\s*(?:>\s*)?(?:\d+[\.\)]|\([0-9]+\))\s*(?:\*\*)?([^\n\:\-\*]+?)(?:\*\*)?(?:\:|\s*\-|\s*—|\n|$)",
                last_assistant_msg,
            )
            for c in numbered:
                clean_c = c.strip(" *#-_`").strip()
                if len(clean_c) >= 3 and clean_c.lower() not in [
                    "core concept", "principles", "application", "step",
                    "note", "summary", "overview", "conclusion",
                ]:
                    concepts.append(clean_c)

            # 2. Bold concept headers: "**Concept Name**"
            if not concepts:
                bold_items = re.findall(r"\*\*([^\*\n]+?)\*\*", last_assistant_msg)
                for b in bold_items:
                    clean_b = b.strip()
                    if (
                        len(clean_b) >= 3
                        and len(clean_b.split()) <= 6
                        and not clean_b.lower().startswith("from ")
                        and not clean_b.lower().startswith("source")
                        and not clean_b.lower().startswith("based on")
                        and not "rate-limited" in clean_b.lower()
                        and not "temporarily" in clean_b.lower()
                        and not "generation model" in clean_b.lower()
                    ):
                        concepts.append(clean_b)

        # 3. Concepts extracted from the last user message (e.g. "What is a Hash Table?")
        # Only fall back to user message if assistant response did not enumerate specific concepts
        if last_user_msg and not concepts:
            cleaned_u = re.sub(
                r"\b(what is|explain|tell me about|how does|can you explain|define|describe|walk me through|summarize|give me|overview of|a|an|the|this|that|pdf|document)\b",
                "",
                last_user_msg,
                flags=re.IGNORECASE,
            ).strip(" ?.!:,`*")
            if (
                len(cleaned_u) >= 3
                and cleaned_u.lower() not in ["summary", "overview", "notes", "file", "all"]
                and cleaned_u not in concepts
            ):
                concepts.append(cleaned_u)

        return concepts, last_doc_id, last_doc_name

    def normalize_semantic_query(self, query: str, doc_name: Optional[str] = None) -> str:
        """
        Strips non-semantic conversational filler and exact filenames from query text
        while preserving technical domain words.
        """
        cleaned = query
        if doc_name:
            cleaned = re.sub(re.escape(doc_name), "", cleaned, flags=re.IGNORECASE)
            fn_no_ext = doc_name.rsplit(".", 1)[0] if "." in doc_name else doc_name
            cleaned = re.sub(re.escape(fn_no_ext), "", cleaned, flags=re.IGNORECASE)

        fillers = [
            r"\b(in this pdf|in this document|from this pdf|from this document|in the file|from the file|in this lecture|from the lecture)\b",
            r"\b(can you please|could you please|please explain|tell me about|tell me|explain to me|walk me through)\b",
            r"\b(in this workspace|from this workspace)\b",
            r"\b(according to this document|based on this document|based on the notes)\b",
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
        All grounding decisions are deferred to retrieval & evidence evaluation.
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
                or (len(fn_no_ext) >= 4 and fn_no_ext in q_lower)
                or (title and len(title) >= 4 and title in q_lower)
            ):
                target_doc = d
                break

        # B. Active current_document_id
        if not target_doc and current_document_id and current_document_id in doc_map:
            target_doc = doc_map[current_document_id]

        # C. If workspace has exactly 1 document or 1 distinct filename, it is the sole active document
        distinct_fns = set(d.get("filename") for d in docs if d.get("filename"))
        if not target_doc and (len(docs) == 1 or len(distinct_fns) == 1) and docs:
            target_doc = docs[0]

        # D. Conversation context inheritance
        history_concepts, last_doc_id, last_doc_name = self.extract_concepts_from_history(recent_history)
        if not target_doc and last_doc_id and last_doc_id in doc_map:
            target_doc = doc_map[last_doc_id]

        target_doc_id = str(target_doc["id"]) if target_doc else None
        target_doc_name = target_doc.get("filename") if target_doc else None
        target_doc_pages = target_doc.get("page_count") if target_doc else None

        # -------------------------------------------------------------
        # 3. PAGE / SLIDE RANGE REFERENCE INTENT (e.g. "pages 5 to 8", "slides 2-4")
        # -------------------------------------------------------------
        range_match = re.search(r"\b(?:pages?|slides?|pgs?)\s*#?\s*(\d+)\s*(?:to|\-|through|\.\.)\s*#?\s*(\d+)\b", q_lower)
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
                semantic_query=f"Pages {p_start} to {p_end} content and summary",
            )

        # -------------------------------------------------------------
        # 4. SINGLE PAGE / SLIDE REFERENCE INTENT (e.g. "page 3", "slide 4", "on slide 2")
        # -------------------------------------------------------------
        page_match = re.search(r"\b(?:page|pg|slide|slide\s+number|page\s+number)\s*#?\s*(\d+)\b", q_lower)
        is_diagram_query = bool(re.search(r"\b(diagram|figure|chart|graph|flowchart|architecture|drawing|illustration)\b", q_lower))
        is_table_query = bool(re.search(r"\b(table|tabular|data\s+grid|matrix)\b", q_lower))

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

            intent_type = "DIAGRAM_FIGURE_QUERY" if is_diagram_query else ("TABLE_QUERY" if is_table_query else "PAGE_REFERENCE")
            return ResolvedQuery(
                intent=intent_type,
                target_document_id=target_doc_id,
                target_document_name=target_doc_name,
                target_document_page_count=target_doc_pages,
                page_number=p_num,
                semantic_query=self.normalize_semantic_query(q_raw, target_doc_name),
                is_visual_query=is_diagram_query,
                is_table_query=is_table_query,
            )

        # -------------------------------------------------------------
        # 5. DIAGRAM / FIGURE / TABLE INTENT (Without explicit page number)
        # -------------------------------------------------------------
        if is_diagram_query or is_table_query:
            norm_q = self.normalize_semantic_query(q_raw, target_doc_name)
            return ResolvedQuery(
                intent="DIAGRAM_FIGURE_QUERY" if is_diagram_query else "TABLE_QUERY",
                target_document_id=target_doc_id,
                target_document_name=target_doc_name,
                target_document_page_count=target_doc_pages,
                semantic_query=norm_q,
                is_visual_query=is_diagram_query,
                is_table_query=is_table_query,
            )

        # -------------------------------------------------------------
        # 6. COMPARE / CONTRAST INTENT
        # -------------------------------------------------------------
        compare_match = re.search(
            r"(?:compare|difference\s+between|contrast|how\s+does\s+(.+?)\s+differ\s+from)\s+(.+?)\s+(?:and|with|to|vs|versus)\s+(.+?)(?:\?|\.|$)",
            q_lower,
        )
        if not compare_match:
            # Short pattern: "X vs Y"
            vs_match = re.search(r"^(.+?)\s+(?:vs\.?|versus)\s+(.+?)(?:\?|\.|$)", q_lower)
            if vs_match:
                ca = vs_match.group(1).strip()
                cb = vs_match.group(2).strip()
                if len(ca) >= 2 and len(cb) >= 2:
                    return ResolvedQuery(
                        intent="COMPARE_CONTRAST",
                        target_document_id=target_doc_id,
                        target_document_name=target_doc_name,
                        target_document_page_count=target_doc_pages,
                        resolved_concept_a=ca,
                        resolved_concept_b=cb,
                        resolved_reference=f"{ca} vs {cb}",
                        semantic_query=f"Compare {ca} and {cb}: differences, mechanisms, performance, tradeoffs",
                    )
        else:
            ca = (compare_match.group(1) or compare_match.group(2)).strip()
            cb = compare_match.group(3).strip()
            if len(ca) >= 2 and len(cb) >= 2:
                return ResolvedQuery(
                    intent="COMPARE_CONTRAST",
                    target_document_id=target_doc_id,
                    target_document_name=target_doc_name,
                    target_document_page_count=target_doc_pages,
                    resolved_concept_a=ca,
                    resolved_concept_b=cb,
                    resolved_reference=f"{ca} vs {cb}",
                    semantic_query=f"Compare {ca} and {cb}: differences, mechanisms, tradeoffs",
                )

        # -------------------------------------------------------------
        # 7. CONTEXTUAL FOLLOW-UP INTENT (Pronouns / Ordinals)
        # -------------------------------------------------------------
        q_no_doc_ref = re.sub(r"\b(this|the)\s+(document|pdf|file|lecture|workspace|notes|material)\b", "", q_lower)
        has_pronoun = bool(re.search(r"\b(its|it's|their|it|this|that|these|those)\b", q_no_doc_ref))
        has_ordinal = bool(re.search(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|last)\s*(concept|point|topic|item|algorithm|part|one)?\b", q_no_doc_ref))
        has_continuation = bool(
            re.search(
                r"\b(simpler terms|in simple terms|elaborate|continue|more details|explain further|break it down|walk me through|just discussed|we discussed|discussed earlier|from earlier|key takeaways|exam points)\b",
                q_no_doc_ref,
            )
        )

        is_followup = bool(recent_history) and (has_pronoun or has_ordinal or has_continuation)

        if is_followup and history_concepts:
            resolved_concept = None
            if re.search(r"\b(first|1st)\b", q_lower) and len(history_concepts) >= 1:
                resolved_concept = history_concepts[0]
            elif re.search(r"\b(second|2nd)\b", q_lower) and len(history_concepts) >= 2:
                resolved_concept = history_concepts[1]
            elif re.search(r"\b(third|3rd)\b", q_lower) and len(history_concepts) >= 3:
                resolved_concept = history_concepts[2]
            elif re.search(r"\b(last)\b", q_lower):
                resolved_concept = history_concepts[-1]
            else:
                resolved_concept = history_concepts[0]

            # Rewrite query with antecedent substituted
            subbed = re.sub(r"\b(its|it's|their)\b", f"the {resolved_concept}'s", q_raw, flags=re.IGNORECASE)
            subbed = re.sub(r"\b(it|this|that)\b", f"'{resolved_concept}'", subbed, flags=re.IGNORECASE)
            subbed = re.sub(
                r"\b(?:the\s+)?(first|1st|second|2nd|third|3rd|last)\s+(concept|point|item|topic|part|algorithm|one)\b",
                f"'{resolved_concept}'",
                subbed,
                flags=re.IGNORECASE,
            )
            subbed = re.sub(
                r"\b(?:from\s+)?(?:what\s+)?(?:we\s+)?(?:just\s+)?discussed(?:\s+earlier)?\b",
                f"'{resolved_concept}'",
                subbed,
                flags=re.IGNORECASE,
            )
            norm_subbed = self.normalize_semantic_query(subbed, target_doc_name)
            sem_q = f"{resolved_concept}: {norm_subbed}" if resolved_concept not in norm_subbed else norm_subbed

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
        # 8. DOCUMENT TOPIC & SUMMARY INTENT
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

        summary_keywords = [
            "summar",
            "what are the concepts",
            "overview of this",
            "overview of the",
            "syllabus",
            "explain this pdf",
            "what is this document about",
            "key takeaways",
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
        # 9. SPECIFIC CONCEPT (Default: all conceptual and paraphrased queries)
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


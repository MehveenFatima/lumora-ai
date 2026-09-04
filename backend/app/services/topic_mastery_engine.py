"""
LumoraAI - Topic Mastery Engine
Concept-to-Topic aggregation, evidence-weighted mastery probability,
confidence heuristics, status classification, and historical trend tracking.
"""
from typing import Dict, Any, List, Optional, Set
import math
import re
from datetime import datetime, timezone

from backend.app.core.logging import get_logger
from backend.app.repositories.bkt import bkt_repo
from backend.app.repositories.topic_mastery import topic_mastery_repo
from backend.app.services.bkt_mastery import bkt_service

logger = get_logger(__name__)

PRESERVED_ACRONYMS = {
    "bfs", "dfs", "dsa", "ssl", "tls", "rsa", "hmac", "mac", "aes", "des",
    "sha", "md5", "api", "http", "https", "tcp", "udp", "ip", "dns", "cpu",
    "ram", "os", "io", "acid", "sql", "nosql", "crud", "jwt", "oauth",
}


def normalize_concept_name(name: str) -> str:
    """Canonicalizes concept name while preserving technical acronyms."""
    if not name:
        return "Core Concept"
    cleaned = re.sub(r"^(?:Page|Unit|Chapter|Section)\s*[\-–:]?\s*\d*\s*[:\-–]?\s*", "", name.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "Core Concept"

    words = cleaned.split(" ")
    normalized_words = []
    for w in words:
        lower_w = w.lower().strip(".,;:()")
        if lower_w in PRESERVED_ACRONYMS:
            prefix = w[:len(w) - len(w.lstrip(".,;:("))]
            suffix = w[len(w.rstrip(".,;:()")):]
            normalized_words.append(prefix + lower_w.upper() + suffix)
        else:
            normalized_words.append(w.capitalize())
    return " ".join(normalized_words)


def normalize_topic_name(name: str) -> str:
    """Canonicalizes topic name while preserving technical acronyms."""
    if not name:
        return "General"
    cleaned = re.sub(r"\s+", " ", name.strip())
    words = cleaned.split(" ")
    normalized = []
    for w in words:
        if w.lower() in PRESERVED_ACRONYMS:
            normalized.append(w.upper())
        else:
            normalized.append(w.capitalize())
    return " ".join(normalized)


class TopicMasteryEngine:
    def __init__(self):
        self.baseline_prior = bkt_service.p_l0  # 0.30

    def calculate_topic_mastery(
        self,
        assessed_concepts: List[Dict[str, Any]],
        total_concept_count: int,
    ) -> Dict[str, Any]:
        """
        Computes evidence-weighted topic mastery probability.
        Uses observation reliability weights w_i = log2(1 + n_i) and coverage blending.
        """
        total_concepts = max(total_concept_count, len(assessed_concepts), 1)
        assessed_count = len(assessed_concepts)
        coverage_ratio = round(assessed_count / total_concepts, 4)

        if not assessed_concepts:
            return {
                "mastery_probability": self.baseline_prior,
                "confidence_level": "none",
                "mastery_status": "not_assessed",
                "coverage_ratio": 0.0,
                "assessed_concept_count": 0,
                "concept_count": total_concepts,
                "total_attempts": 0,
                "total_correct": 0,
                "recent_accuracy": 0.0,
                "average_response_time_ms": 0,
            }

        weighted_p_sum = 0.0
        weight_sum = 0.0
        total_attempts = 0
        total_correct = 0
        total_time_weighted = 0

        for c in assessed_concepts:
            n_attempts = max(1, c.get("attempts_count", 1))
            n_correct = c.get("correct_count", 0)
            p_m = float(c.get("p_mastery", self.baseline_prior))
            avg_time = c.get("average_response_time_ms", c.get("last_response_time_ms", 0))

            w_i = math.log2(1 + n_attempts)
            weighted_p_sum += w_i * p_m
            weight_sum += w_i

            total_attempts += n_attempts
            total_correct += n_correct
            total_time_weighted += avg_time * n_attempts

        assessed_avg_p = (weighted_p_sum / weight_sum) if weight_sum > 0 else self.baseline_prior

        # Blending with baseline prior according to concept coverage
        topic_p = (coverage_ratio * assessed_avg_p) + ((1.0 - coverage_ratio) * self.baseline_prior)
        topic_p = max(0.01, min(0.99, round(topic_p, 4)))

        # Evidence confidence heuristic
        if total_attempts < 4 or coverage_ratio < 0.30:
            confidence = "low"
        elif total_attempts >= 12 and coverage_ratio >= 0.60:
            confidence = "high"
        else:
            confidence = "moderate"

        # Mastery status
        if confidence == "low":
            status = "low_evidence" if topic_p >= 0.70 else "developing"
        elif topic_p >= 0.80:
            status = "strong"
        elif topic_p >= 0.60:
            status = "developing"
        elif topic_p >= 0.40:
            status = "needs_review"
        else:
            status = "critical_gap"

        recent_acc = round(total_correct / total_attempts, 4) if total_attempts > 0 else 0.0
        avg_resp_time = int(total_time_weighted / total_attempts) if total_attempts > 0 else 0

        return {
            "mastery_probability": topic_p,
            "confidence_level": confidence,
            "mastery_status": status,
            "coverage_ratio": coverage_ratio,
            "assessed_concept_count": assessed_count,
            "concept_count": total_concepts,
            "total_attempts": total_attempts,
            "total_correct": total_correct,
            "recent_accuracy": recent_acc,
            "average_response_time_ms": avg_resp_time,
        }

    async def recalculate_topic(
        self,
        workspace_id: str,
        topic: str,
        known_topic_concepts: Optional[List[str]] = None,
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        norm_topic = normalize_topic_name(topic)
        all_concepts = await bkt_repo.list_concept_mastery(workspace_id, user_id)
        
        matching_concepts = [
            c for c in all_concepts
            if normalize_topic_name(c.get("topic", "")) == norm_topic
        ]

        if known_topic_concepts:
            total_concept_count = max(len(known_topic_concepts), len(matching_concepts))
        else:
            total_concept_count = max(1, len(matching_concepts))

        calc = self.calculate_topic_mastery(matching_concepts, total_concept_count)

        gaps = await bkt_repo.list_knowledge_gaps(workspace_id, user_id)
        topic_gaps = [
            g for g in gaps
            if normalize_topic_name(g.get("topic", "")) == norm_topic
        ]
        avg_gap_priority = (
            sum(g.get("gap_priority", 0.0) for g in topic_gaps) / len(topic_gaps)
        ) if topic_gaps else 0.0

        recent_snapshots = await topic_mastery_repo.get_recent_snapshots(
            workspace_id=workspace_id,
            entity_type="topic",
            entity_id=norm_topic,
            limit=2,
            user_id=user_id,
        )
        if len(recent_snapshots) >= 1:
            prev_p = recent_snapshots[0].get("mastery_probability", self.baseline_prior)
            delta = calc["mastery_probability"] - prev_p
            if delta >= 0.03:
                trend = "improving"
            elif delta <= -0.03:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        updated = await topic_mastery_repo.upsert_topic_mastery(
            workspace_id=workspace_id,
            topic=norm_topic,
            mastery_probability=calc["mastery_probability"],
            confidence_level=calc["confidence_level"],
            mastery_status=calc["mastery_status"],
            trend=trend,
            concept_count=calc["concept_count"],
            assessed_concept_count=calc["assessed_concept_count"],
            coverage_ratio=calc["coverage_ratio"],
            attempt_count=calc["total_attempts"],
            correct_count=calc["total_correct"],
            recent_accuracy=calc["recent_accuracy"],
            average_response_time_ms=calc["average_response_time_ms"],
            gap_priority=avg_gap_priority,
            last_assessed_at=datetime.now(timezone.utc),
            user_id=user_id,
        )

        await topic_mastery_repo.record_snapshot(
            workspace_id=workspace_id,
            entity_type="topic",
            entity_id=norm_topic,
            mastery_probability=calc["mastery_probability"],
            confidence_level=calc["confidence_level"],
            gap_priority=avg_gap_priority,
            attempt_count=calc["total_attempts"],
            snapshot_event="attempt",
            user_id=user_id,
        )

        return updated

    async def recalculate_all_workspace_topics(
        self,
        workspace_id: str,
        user_id: str = "default_user",
    ) -> List[Dict[str, Any]]:
        all_concepts = await bkt_repo.list_concept_mastery(workspace_id, user_id)
        distinct_topics = {
            normalize_topic_name(c.get("topic", "General"))
            for c in all_concepts
            if c.get("topic")
        }

        # If no concept mastery records exist yet, discover topics from ingested document chunks
        if not distinct_topics:
            try:
                from backend.app.repositories.documents import document_repo
                from backend.app.repositories.chunks import chunk_repo
                docs = await document_repo.list_by_workspace(workspace_id)
                for doc in docs:
                    chunks = await chunk_repo.get_chunks_by_document(workspace_id, str(doc["id"]))
                    for ch in chunks:
                        meta = ch.get("metadata", {}) or {}
                        t = meta.get("topic")
                        if not t and ch.get("heading") and not re.match(r"^(?:Page|Slide|Unit|Chapter)\s*\d*", str(ch["heading"]), flags=re.IGNORECASE):
                            t = ch["heading"]
                        if t:
                            norm = normalize_topic_name(str(t))
                            if norm and norm.lower() != "general":
                                distinct_topics.add(norm)
                        text = ch.get("text", "")
                        m = re.search(r"Topic:\s*([^.\n]+)", text, flags=re.IGNORECASE)
                        if m:
                            norm = normalize_topic_name(m.group(1))
                            if norm:
                                distinct_topics.add(norm)
            except Exception as e:
                logger.warning(f"Error discovering topics from document chunks: {e}")

        results = []
        for t in sorted(list(distinct_topics)):
            res = await self.recalculate_topic(workspace_id, t, user_id=user_id)
            results.append(res)
        return results


topic_mastery_engine = TopicMasteryEngine()

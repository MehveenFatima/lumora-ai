"""
LumoraAI - Learner Knowledge Profile Service
Aggregates concept and topic mastery states into a workspace-scoped Learner Knowledge Profile.
Generates telemetry, gap rankings, trends, and structured recommendation payloads.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.core.logging import get_logger
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.bkt import bkt_repo
from backend.app.repositories.topic_mastery import topic_mastery_repo
from backend.app.repositories.quizzes import quiz_repo
from backend.app.services.topic_mastery_engine import topic_mastery_engine, normalize_topic_name

logger = get_logger(__name__)


class LearnerProfileService:
    async def get_learner_profile(
        self,
        workspace_id: str,
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()

        ws = await workspace_repo.get_by_id(workspace_id)
        if not ws:
            raise ValueError(f"Workspace '{workspace_id}' not found.")

        docs = await document_repo.list_by_workspace(workspace_id)
        if not docs:
            return {
                "workspace_id": workspace_id,
                "status": "not_assessed",
                "message": f"Upload and index learning materials in workspace '{workspace_id}' to begin building your learner profile.",
                "overall": {
                    "mastery_percentage": 0,
                    "mastery_probability": 0.0,
                    "mastery_delta": 0,
                    "status": "not_assessed",
                    "confidence": "none",
                    "coverage_ratio": 0.0,
                    "assessed_concepts_count": 0,
                    "total_concepts_count": 0,
                    "assessed_topics_count": 0,
                    "total_topics_count": 0,
                },
                "strongest_topics": [],
                "weakest_topics": [],
                "top_knowledge_gaps": [],
                "improving_topics": [],
                "declining_topics": [],
                "recent_performance": {
                    "quizzes_completed": 0,
                    "total_attempts": 0,
                    "accuracy_percentage": 0,
                    "average_response_time_seconds": 0.0,
                },
                "recommendations": [],
                "last_updated": now_iso,
            }

        topics = await topic_mastery_repo.list_topic_mastery(workspace_id, user_id)
        concepts = await bkt_repo.list_concept_mastery(workspace_id, user_id)
        gaps = await bkt_repo.list_knowledge_gaps(workspace_id, user_id)
        attempts = await quiz_repo.list_attempts_by_workspace(workspace_id, user_id)
        sessions = await quiz_repo.list_sessions_by_workspace(workspace_id)

        if not topics and concepts:
            topics = await topic_mastery_engine.recalculate_all_workspace_topics(workspace_id, user_id)

        if not concepts and not attempts:
            return {
                "workspace_id": workspace_id,
                "status": "not_assessed",
                "message": "No quiz assessments completed yet. Take an adaptive quiz to begin profiling concept mastery.",
                "overall": {
                    "mastery_percentage": 0,
                    "mastery_probability": 0.30,
                    "mastery_delta": 0,
                    "status": "not_assessed",
                    "confidence": "none",
                    "coverage_ratio": 0.0,
                    "assessed_concepts_count": 0,
                    "total_concepts_count": 0,
                    "assessed_topics_count": 0,
                    "total_topics_count": max(1, len(topics)),
                },
                "strongest_topics": [],
                "weakest_topics": [],
                "top_knowledge_gaps": [],
                "improving_topics": [],
                "declining_topics": [],
                "recent_performance": {
                    "quizzes_completed": 0,
                    "total_attempts": 0,
                    "accuracy_percentage": 0,
                    "average_response_time_seconds": 0.0,
                },
                "recommendations": [],
                "last_updated": now_iso,
            }

        total_attempts = len(attempts)
        correct_attempts = sum(1 for a in attempts if a.get("is_correct"))
        accuracy_pct = round((correct_attempts / total_attempts) * 100) if total_attempts > 0 else 0
        total_time_s = sum(a.get("response_time_ms", 0) for a in attempts) / 1000.0
        avg_time_s = round(total_time_s / total_attempts, 1) if total_attempts > 0 else 0.0

        assessed_concepts_count = len(concepts)
        total_concepts_estimate = max(assessed_concepts_count, sum(t.get("concept_count", 1) for t in topics) or 1)
        workspace_coverage = round(assessed_concepts_count / total_concepts_estimate, 4)

        if topics:
            weighted_mastery_sum = sum(
                t.get("mastery_probability", 0.30) * max(1, t.get("attempt_count", 1))
                for t in topics
            )
            weight_total = sum(max(1, t.get("attempt_count", 1)) for t in topics)
            overall_prob = round(weighted_mastery_sum / weight_total, 4) if weight_total > 0 else 0.30
        else:
            overall_prob = round(
                sum(c.get("p_mastery", 0.30) for c in concepts) / len(concepts), 4
            ) if concepts else 0.30

        overall_pct = int(round(overall_prob * 100))

        if total_attempts < 5:
            ws_conf = "low"
        elif total_attempts < 15:
            ws_conf = "moderate"
        else:
            ws_conf = "high"

        if ws_conf == "low":
            ws_status = "low_evidence" if overall_pct >= 70 else "developing"
        elif overall_pct >= 80:
            ws_status = "strong"
        elif overall_pct >= 60:
            ws_status = "developing"
        elif overall_pct >= 40:
            ws_status = "needs_review"
        else:
            ws_status = "critical_gap"

        prev_mastery = ws.get("overall_mastery", 0)
        mastery_delta = overall_pct - prev_mastery if prev_mastery > 0 else 0

        try:
            await workspace_repo.update_mastery(
                workspace_id=workspace_id,
                overall_mastery=overall_pct,
                mastery_delta=mastery_delta,
            )
        except Exception as e:
            logger.warning(f"Failed to sync workspace mastery update: {e}")

        sorted_topics = sorted(topics, key=lambda x: x.get("mastery_probability", 0.30), reverse=True)
        strongest = [t for t in sorted_topics if t.get("mastery_probability", 0.0) >= 0.60]
        weakest = [t for t in sorted_topics if t.get("mastery_probability", 0.0) < 0.60]
        improving = [t for t in sorted_topics if t.get("trend") == "improving"]
        declining = [t for t in sorted_topics if t.get("trend") == "declining"]

        concept_lookup = {c.get("concept"): c for c in concepts}
        enriched_gaps = []
        for g in gaps[:5]:
            c_info = concept_lookup.get(g.get("concept"), {})
            g_copy = dict(g)
            g_copy["p_mastery"] = c_info.get("p_mastery", 0.30)
            enriched_gaps.append(g_copy)

        recommendations = []
        for g in gaps[:5]:
            c_info = concept_lookup.get(g.get("concept"), {})
            recommendations.append({
                "workspace_id": workspace_id,
                "topic": g.get("topic"),
                "concept": g.get("concept"),
                "mastery_probability": c_info.get("p_mastery", 0.30),
                "gap_priority": g.get("gap_priority", 0.50),
                "confidence": c_info.get("confidence_level", "low"),
                "trend": c_info.get("trend", "insufficient_data"),
                "recent_accuracy": c_info.get("recent_accuracy", 0.0),
                "repeated_errors": c_info.get("repeated_error_count", 0),
                "recommended_action": g.get("recommended_action", "targeted_practice"),
            })

        completed_sessions = sum(1 for s in sessions if s.get("status") == "completed")

        return {
            "workspace_id": workspace_id,
            "status": "assessed",
            "message": "Learner knowledge profile successfully generated.",
            "overall": {
                "mastery_percentage": overall_pct,
                "mastery_probability": overall_prob,
                "mastery_delta": mastery_delta,
                "status": ws_status,
                "confidence": ws_conf,
                "coverage_ratio": workspace_coverage,
                "assessed_concepts_count": assessed_concepts_count,
                "total_concepts_count": total_concepts_estimate,
                "assessed_topics_count": len(topics),
                "total_topics_count": max(1, len(topics)),
            },
            "strongest_topics": strongest[:5],
            "weakest_topics": weakest[:5],
            "top_knowledge_gaps": enriched_gaps,
            "improving_topics": improving[:5],
            "declining_topics": declining[:5],
            "recent_performance": {
                "quizzes_completed": completed_sessions,
                "total_attempts": total_attempts,
                "accuracy_percentage": accuracy_pct,
                "average_response_time_seconds": avg_time_s,
            },
            "recommendations": recommendations,
            "last_updated": now_iso,
        }


learner_profile_service = LearnerProfileService()

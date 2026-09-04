"""
LumoraAI - Knowledge Gap Engine
Multi-signal priority scoring and status categorization for targeted adaptive learning.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# Configurable Weights for Knowledge Gap Scoring (Sum = 1.0)
W_MASTERY = 0.35     # 1 - P(K)
W_ERROR = 0.25       # Recent error rate
W_REPEAT = 0.20      # Repeated concept mistakes
W_DIFFICULTY = 0.10  # Struggle on current difficulty level
W_TIME = 0.10        # Hesitation / slow response time factor

# Status Bands (0.0 to 1.0)
BAND_STRONG_MAX = 0.29
BAND_DEVELOPING_MAX = 0.49
BAND_ATTENTION_MAX = 0.69

# Response Time Reference
SLOW_TIME_THRESHOLD_MS = 40000


class KnowledgeGapEngine:
    def __init__(
        self,
        w_mastery: float = W_MASTERY,
        w_error: float = W_ERROR,
        w_repeat: float = W_REPEAT,
        w_difficulty: float = W_DIFFICULTY,
        w_time: float = W_TIME,
    ):
        self.w_mastery = w_mastery
        self.w_error = w_error
        self.w_repeat = w_repeat
        self.w_difficulty = w_difficulty
        self.w_time = w_time

    def compute_gap_priority(
        self,
        p_mastery: float,
        recent_error_rate: float,
        repeated_error_count: int,
        difficulty_level: int,
        average_response_time_ms: int,
    ) -> Dict[str, Any]:
        """
        Calculates normalized knowledge gap priority score in [0.0, 1.0].
        """
        # 1. Mastery component (higher gap if mastery is low)
        mastery_term = max(0.0, min(1.0, 1.0 - p_mastery))

        # 2. Error rate component
        error_term = max(0.0, min(1.0, recent_error_rate))

        # 3. Repeated error factor: 0 mistakes = 0.0, 1 = 0.4, 2 = 0.8, 3+ = 1.0
        repeat_term = min(1.0, repeated_error_count * 0.4)

        # 4. Difficulty struggle: failing at higher difficulty is more concerning if unmastered
        # But failing at difficulty 1 indicates fundamental gap
        difficulty_term = 1.0 if difficulty_level == 1 and recent_error_rate > 0 else (0.6 if difficulty_level == 2 else 0.3)

        # 5. Hesitation / response time factor
        time_term = min(1.0, average_response_time_ms / SLOW_TIME_THRESHOLD_MS)

        raw_priority = (
            (self.w_mastery * mastery_term)
            + (self.w_error * error_term)
            + (self.w_repeat * repeat_term)
            + (self.w_difficulty * difficulty_term)
            + (self.w_time * time_term)
        )
        priority = round(max(0.0, min(1.0, raw_priority)), 4)

        # Status categorization
        if priority <= BAND_STRONG_MAX:
            status = "strong"
            action = "advance_difficulty"
        elif priority <= BAND_DEVELOPING_MAX:
            status = "developing"
            action = "continue_practice"
        elif priority <= BAND_ATTENTION_MAX:
            status = "needs_attention"
            action = "targeted_reinforcement"
        else:
            status = "critical_gap"
            action = "foundational_review"

        return {
            "gap_priority": priority,
            "status": status,
            "recommended_action": action,
            "signals": {
                "mastery_term": round(mastery_term, 4),
                "error_term": round(error_term, 4),
                "repeat_term": round(repeat_term, 4),
                "difficulty_term": round(difficulty_term, 4),
                "time_term": round(time_term, 4),
            },
        }

    def evaluate_concept_performance(
        self,
        concept: str,
        topic: str,
        p_mastery: float,
        attempts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Evaluates a concept based on its attempt history.
        """
        if not attempts:
            return {
                "concept": concept,
                "topic": topic,
                "p_mastery": p_mastery,
                "attempts_count": 0,
                "correct_count": 0,
                "accuracy_percentage": 0,
                "gap_priority": 0.50,
                "status": "developing",
                "recommended_action": "initial_assessment",
            }

        total = len(attempts)
        correct = sum(1 for a in attempts if a.get("is_correct"))
        accuracy = round((correct / total) * 100) if total > 0 else 0

        # Recent 3 attempts
        recent = attempts[-3:]
        recent_err_rate = sum(1 for a in recent if not a.get("is_correct")) / len(recent)

        # Consecutive/repeated errors
        repeated_errors = 0
        for a in reversed(attempts):
            if not a.get("is_correct"):
                repeated_errors += 1
            else:
                break

        # Average response time
        times = [a.get("response_time_ms", 0) for a in attempts if a.get("response_time_ms", 0) > 0]
        avg_time = int(sum(times) / len(times)) if times else 0

        last_diff = attempts[-1].get("difficulty", 2)

        gap_info = self.compute_gap_priority(
            p_mastery=p_mastery,
            recent_error_rate=recent_err_rate,
            repeated_error_count=repeated_errors,
            difficulty_level=last_diff,
            average_response_time_ms=avg_time,
        )

        return {
            "concept": concept,
            "topic": topic,
            "p_mastery": p_mastery,
            "mastery_percentage": int(round(p_mastery * 100)),
            "attempts_count": total,
            "correct_count": correct,
            "accuracy_percentage": accuracy,
            "average_response_time_ms": avg_time,
            "gap_priority": gap_info["gap_priority"],
            "status": gap_info["status"],
            "recommended_action": gap_info["recommended_action"],
            "signals": gap_info["signals"],
        }


knowledge_gap_engine = KnowledgeGapEngine()

from typing import List, Dict, Any, Optional, Tuple
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# Configurable adaptation thresholds
FAST_RESPONSE_THRESHOLD_MS = 15000  # < 15s is considered fast
SLOW_RESPONSE_THRESHOLD_MS = 45000  # > 45s is considered slow
HIGH_ACCURACY_THRESHOLD = 0.75      # >= 75% accuracy
LOW_ACCURACY_THRESHOLD = 0.40       # <= 40% accuracy


class AdaptiveDecision:
    def __init__(
        self,
        next_difficulty: int,
        target_concept: Optional[str] = None,
        target_topic: Optional[str] = None,
        is_reinforcement: bool = False,
        reason: str = "Standard progression",
    ):
        self.next_difficulty = next_difficulty
        self.target_concept = target_concept
        self.target_topic = target_topic
        self.is_reinforcement = is_reinforcement
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "next_difficulty": self.next_difficulty,
            "next_difficulty_label": {1: "easy", 2: "medium", 3: "hard"}.get(self.next_difficulty, "medium"),
            "target_concept": self.target_concept,
            "target_topic": self.target_topic,
            "is_reinforcement": self.is_reinforcement,
            "reason": self.reason,
        }


class AdaptiveQuizEngine:
    def evaluate_next_step(
        self,
        session_attempts: List[Dict[str, Any]],
        session_questions: List[Dict[str, Any]],
        current_difficulty: int = 2,
    ) -> AdaptiveDecision:
        """
        Determines the next question difficulty and concept target based on multi-signal evaluation.
        """
        if not session_attempts:
            return AdaptiveDecision(
                next_difficulty=current_difficulty,
                reason="Initial baseline assessment question",
            )

        # 1. Map questions for metadata access
        questions_by_id = {str(q["id"]): q for q in session_questions}

        # 2. Check Repeated-Mistake on Same Concept
        concept_mistakes: Dict[str, int] = {}
        for att in session_attempts:
            if not att.get("is_correct"):
                q = questions_by_id.get(str(att.get("question_id")), {})
                c_name = q.get("concept") or "General"
                concept_mistakes[c_name] = concept_mistakes.get(c_name, 0) + 1

        last_attempt = session_attempts[-1]
        last_question = questions_by_id.get(str(last_attempt.get("question_id")), {})
        last_concept = last_question.get("concept") or "General"
        last_topic = last_question.get("topic") or "General"

        if concept_mistakes.get(last_concept, 0) >= 2 and not last_attempt.get("is_correct"):
            # Trigger immediate reinforcement at equal or lower difficulty
            reinforced_diff = max(1, current_difficulty - 1)
            return AdaptiveDecision(
                next_difficulty=reinforced_diff,
                target_concept=last_concept,
                target_topic=last_topic,
                is_reinforcement=True,
                reason=f"Repeated mistake detected on concept '{last_concept}'. Providing reinforcement question.",
            )

        # 3. Calculate Recent Accuracy & Response Time Signals
        recent_attempts = session_attempts[-3:]
        correct_count = sum(1 for a in recent_attempts if a.get("is_correct"))
        recent_acc = correct_count / len(recent_attempts)
        last_time_ms = last_attempt.get("response_time_ms", 30000)
        last_correct = last_attempt.get("is_correct", False)

        # 4. Multi-Signal Adaptive Logic
        if last_correct:
            if last_time_ms <= FAST_RESPONSE_THRESHOLD_MS and recent_acc >= HIGH_ACCURACY_THRESHOLD:
                # Fast & High Accuracy -> Increase Difficulty (up to 3)
                next_diff = min(3, current_difficulty + 1)
                reason = "Strong accuracy and fast response time. Elevating to harder difficulty."
            elif recent_acc >= HIGH_ACCURACY_THRESHOLD:
                next_diff = min(3, current_difficulty + 1 if current_difficulty == 1 else current_difficulty)
                reason = "Consistent correct answers. Maintaining or advancing difficulty."
            else:
                next_diff = current_difficulty
                reason = "Correct answer submitted. Maintaining current level."
        else:
            if last_time_ms >= SLOW_RESPONSE_THRESHOLD_MS or recent_acc <= LOW_ACCURACY_THRESHOLD:
                # Slow & Low Accuracy -> Step Down Difficulty (down to 1)
                next_diff = max(1, current_difficulty - 1)
                reason = "Hesitation and incorrect answer detected. Decreasing difficulty for foundational reinforcement."
            else:
                next_diff = current_difficulty
                reason = "Incorrect answer. Keeping current level for concept validation."

        return AdaptiveDecision(
            next_difficulty=next_diff,
            target_topic=None,  # Cycle across topics
            target_concept=None,
            is_reinforcement=False,
            reason=reason,
        )


adaptive_quiz_engine = AdaptiveQuizEngine()

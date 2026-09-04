"""
LumoraAI - Bayesian Knowledge Tracing (BKT) Service
Standard mathematical model for concept-level mastery estimation.
"""
from typing import Dict, Any, Optional
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# Default Canonical BKT Parameters
DEFAULT_P_L0 = 0.30  # Initial probability of knowing the concept
DEFAULT_P_T  = 0.15  # Probability of learning concept after practice opportunity
DEFAULT_P_G  = 0.20  # Probability of guessing correctly without mastery
DEFAULT_P_S  = 0.10  # Probability of slipping (answering wrong despite mastery)


class BKTMasteryService:
    def __init__(
        self,
        p_l0: float = DEFAULT_P_L0,
        p_t: float = DEFAULT_P_T,
        p_g: float = DEFAULT_P_G,
        p_s: float = DEFAULT_P_S,
    ):
        self.p_l0 = p_l0
        self.p_t = p_t
        self.p_g = p_g
        self.p_s = p_s

    def calculate_p_correct(self, p_k: float) -> float:
        """
        Calculates P(Correct) = P(K)*(1 - P(S)) + (1 - P(K))*P(G)
        """
        p_k = max(0.001, min(0.999, p_k))
        return (p_k * (1.0 - self.p_s)) + ((1.0 - p_k) * self.p_g)

    def update_posterior(self, p_k: float, is_correct: bool) -> float:
        """
        Calculates posterior probability P(K | Observation).
        """
        p_k = max(0.001, min(0.999, p_k))
        p_correct = self.calculate_p_correct(p_k)

        if is_correct:
            numerator = p_k * (1.0 - self.p_s)
            posterior = numerator / p_correct if p_correct > 0 else p_k
        else:
            p_incorrect = 1.0 - p_correct
            numerator = p_k * self.p_s
            posterior = numerator / p_incorrect if p_incorrect > 0 else p_k

        return max(0.001, min(0.999, posterior))

    def apply_learning_transition(self, posterior_p_k: float) -> float:
        """
        Applies learning transition: P(K_next) = posterior + (1 - posterior) * P(T)
        """
        posterior = max(0.001, min(0.999, posterior_p_k))
        p_next = posterior + ((1.0 - posterior) * self.p_t)
        return max(0.001, min(0.999, p_next))

    def update_mastery(self, current_p_k: float, is_correct: bool) -> float:
        """
        Full BKT cycle: Posterior Update -> Transition Update.
        """
        posterior = self.update_posterior(current_p_k, is_correct)
        new_mastery = self.apply_learning_transition(posterior)
        return round(new_mastery, 6)

    def get_initial_prior(self, existing_history_p_k: Optional[float] = None) -> float:
        """
        Returns existing prior if present and valid, otherwise default P(L0).
        """
        if existing_history_p_k is not None and 0.0 < existing_history_p_k < 1.0:
            return existing_history_p_k
        return self.p_l0

    @staticmethod
    def format_display_percentage(p_k: float) -> int:
        """
        Formats BKT probability into clean integer percentage (0-100) for UI.
        """
        return int(round(max(0.0, min(1.0, p_k)) * 100))

    @staticmethod
    def get_mastery_band(p_k: float) -> str:
        """
        Returns standard mastery classification based on BKT probability.
        """
        if p_k >= 0.75:
            return "mastered"
        if p_k >= 0.45:
            return "proficient"
        return "review_needed"


bkt_service = BKTMasteryService()

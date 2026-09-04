"""
LumoraAI - Adaptive Question Selector
Determines target concepts, difficulty calibration, and explainability decisions.
"""
from typing import List, Dict, Any, Optional
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class SelectionDecision:
    def __init__(
        self,
        target_concept: str,
        target_topic: str,
        difficulty: int,
        is_reinforcement: bool,
        reason: str,
    ):
        self.target_concept = target_concept
        self.target_topic = target_topic
        self.difficulty = difficulty
        self.is_reinforcement = is_reinforcement
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_concept": self.target_concept,
            "target_topic": self.target_topic,
            "difficulty": self.difficulty,
            "difficulty_label": {1: "easy", 2: "medium", 3: "hard"}.get(self.difficulty, "medium"),
            "is_reinforcement": self.is_reinforcement,
            "reason": self.reason,
        }


class AdaptiveQuestionSelector:
    def select_next_question_target(
        self,
        concept_evaluations: List[Dict[str, Any]],
        available_concepts: List[Dict[str, str]],
        current_question_index: int,
        target_total_questions: int,
    ) -> SelectionDecision:
        """
        Selects target concept and calibrated difficulty level.
        """
        if not concept_evaluations:
            # Cold start: select first available concept from source inventory
            first_c = available_concepts[0] if available_concepts else {"concept": "Key Principles", "topic": "General"}
            return SelectionDecision(
                target_concept=first_c["concept"],
                target_topic=first_c["topic"],
                difficulty=2,
                is_reinforcement=False,
                reason="Initial baseline assessment across curriculum concepts.",
            )

        # Sort evaluations by gap priority descending (highest gap first)
        ranked_gaps = sorted(concept_evaluations, key=lambda x: x.get("gap_priority", 0.0), reverse=True)
        top_gap = ranked_gaps[0]

        # Concepts already assessed
        assessed_concepts = {e["concept"] for e in concept_evaluations}
        unassessed = [c for c in available_concepts if c["concept"] not in assessed_concepts]

        # In diagnostic stage (first 5 questions), prioritize breadth across unassessed concepts
        if current_question_index < target_total_questions and unassessed:
            next_unassessed = unassessed[0]
            return SelectionDecision(
                target_concept=next_unassessed["concept"],
                target_topic=next_unassessed["topic"],
                difficulty=2,
                is_reinforcement=False,
                reason=f"Diagnostic exploration: Assessing concept '{next_unassessed['concept']}'.",
            )

        # Targeted adaptive reinforcement / validation
        # If top gap is critical or needs attention, reinforce it
        if top_gap.get("status") in {"critical_gap", "needs_attention"}:
            p_m = top_gap.get("p_mastery", 0.3)
            # Level 1 if very low, else Level 2
            target_diff = 1 if p_m < 0.40 else 2
            return SelectionDecision(
                target_concept=top_gap["concept"],
                target_topic=top_gap["topic"],
                difficulty=target_diff,
                is_reinforcement=True,
                reason=f"Targeted reinforcement on '{top_gap['concept']}' (Mastery: {int(p_m*100)}%, Gap Score: {top_gap['gap_priority']}).",
            )

        # If learner is strong on tested concepts, challenge them or explore remaining
        if unassessed:
            next_c = unassessed[0]
            return SelectionDecision(
                target_concept=next_c["concept"],
                target_topic=next_c["topic"],
                difficulty=2,
                is_reinforcement=False,
                reason=f"Expanding breadth: Exploring curriculum concept '{next_c['concept']}'.",
            )

        # All concepts assessed and reasonably mastered -> advanced validation
        target_diff = 3 if top_gap.get("p_mastery", 0.5) >= 0.70 else 2
        return SelectionDecision(
            target_concept=top_gap["concept"],
            target_topic=top_gap["topic"],
            difficulty=target_diff,
            is_reinforcement=False,
            reason=f"Advanced mastery validation on '{top_gap['concept']}' at Level {target_diff}.",
        )

    def select_batch_targets(
        self,
        concept_evaluations: List[Dict[str, Any]],
        available_concepts: List[Dict[str, str]],
        batch_size: int = 5,
    ) -> List[SelectionDecision]:
        """
        Selects a diverse list of targets for an entire batch (e.g. Batch 2).
        Prioritizes top knowledge gaps while reserving at least 1 slot for breadth/challenge.
        """
        decisions: List[SelectionDecision] = []
        ranked_gaps = sorted(concept_evaluations, key=lambda x: x.get("gap_priority", 0.0), reverse=True)
        assessed = {e["concept"] for e in concept_evaluations}
        unassessed = [c for c in available_concepts if c["concept"] not in assessed]

        # Reserve slots: up to 3-4 slots for top weak concepts, remaining for breadth/exploration
        weak_slots = min(len(ranked_gaps), batch_size - (1 if unassessed else 0))
        for i in range(weak_slots):
            c_eval = ranked_gaps[i]
            p_m = c_eval.get("p_mastery", 0.3)
            diff = 1 if p_m < 0.40 else (3 if p_m >= 0.75 else 2)
            decisions.append(
                SelectionDecision(
                    target_concept=c_eval["concept"],
                    target_topic=c_eval["topic"],
                    difficulty=diff,
                    is_reinforcement=True,
                    reason=f"Reinforcing identified gap '{c_eval['concept']}' (Mastery: {int(p_m*100)}%).",
                )
            )

        # Fill remaining slots with unassessed or alternating concepts
        idx = 0
        while len(decisions) < batch_size:
            if unassessed:
                c = unassessed.pop(0)
                decisions.append(
                    SelectionDecision(
                        target_concept=c["concept"],
                        target_topic=c["topic"],
                        difficulty=2,
                        is_reinforcement=False,
                        reason=f"Exploratory assessment on '{c['concept']}'.",
                    )
                )
            elif ranked_gaps:
                c_eval = ranked_gaps[idx % len(ranked_gaps)]
                idx += 1
                decisions.append(
                    SelectionDecision(
                        target_concept=c_eval["concept"],
                        target_topic=c_eval["topic"],
                        difficulty=2,
                        is_reinforcement=True,
                        reason=f"Follow-up verification on '{c_eval['concept']}'.",
                    )
                )
            elif available_concepts:
                c = available_concepts[idx % len(available_concepts)]
                idx += 1
                decisions.append(
                    SelectionDecision(
                        target_concept=c["concept"],
                        target_topic=c["topic"],
                        difficulty=2,
                        is_reinforcement=False,
                        reason=f"Core curriculum assessment on '{c['concept']}'.",
                    )
                )
            else:
                decisions.append(
                    SelectionDecision(
                        target_concept="Key Principles",
                        target_topic="General",
                        difficulty=2,
                        is_reinforcement=False,
                        reason="Standard concept check.",
                    )
                )

        return decisions


adaptive_question_selector = AdaptiveQuestionSelector()

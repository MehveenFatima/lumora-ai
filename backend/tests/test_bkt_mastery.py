"""
Unit Tests for Bayesian Knowledge Tracing (BKT) Service
"""
import pytest
from backend.app.services.bkt_mastery import BKTMasteryService, DEFAULT_P_L0, DEFAULT_P_T, DEFAULT_P_G, DEFAULT_P_S


def test_bkt_initial_prior():
    service = BKTMasteryService()
    assert service.get_initial_prior() == DEFAULT_P_L0
    assert service.get_initial_prior(0.55) == 0.55
    # Invalid or zero prior falls back to L0
    assert service.get_initial_prior(0.0) == DEFAULT_P_L0
    assert service.get_initial_prior(1.5) == DEFAULT_P_L0


def test_bkt_correct_answer_increases_mastery():
    service = BKTMasteryService()
    p_k_initial = 0.30
    p_k_next = service.update_mastery(p_k_initial, is_correct=True)
    assert p_k_next > p_k_initial, f"Mastery should increase on correct answer: {p_k_next} vs {p_k_initial}"
    # Calculate manual expected:
    # P(C) = 0.30 * 0.90 + 0.70 * 0.20 = 0.27 + 0.14 = 0.41
    # P(K|C) = 0.27 / 0.41 = 0.658536
    # P(K_next) = 0.658536 + (1 - 0.658536) * 0.15 = 0.658536 + 0.051219 = 0.709756
    assert abs(p_k_next - 0.709756) < 0.001


def test_bkt_incorrect_answer_decreases_mastery():
    service = BKTMasteryService()
    p_k_initial = 0.70
    p_k_next = service.update_mastery(p_k_initial, is_correct=False)
    assert p_k_next < p_k_initial, f"Mastery should decrease on incorrect answer: {p_k_next} vs {p_k_initial}"
    # Manual expected:
    # P(C) = 0.70 * 0.90 + 0.30 * 0.20 = 0.63 + 0.06 = 0.69
    # P(~C) = 0.31
    # P(K|~C) = (0.70 * 0.10) / 0.31 = 0.07 / 0.31 = 0.225806
    # P(K_next) = 0.225806 + (1 - 0.225806) * 0.15 = 0.225806 + 0.116129 = 0.341935
    assert abs(p_k_next - 0.341935) < 0.001


def test_bkt_learning_transition_property():
    service = BKTMasteryService(p_t=0.20)
    # If posterior is 0.5, transition must increase it
    p_next = service.apply_learning_transition(0.50)
    assert p_next == 0.50 + 0.50 * 0.20
    assert p_next == 0.60


def test_bkt_repeated_practice_convergence():
    service = BKTMasteryService()
    p_k = service.get_initial_prior()
    for _ in range(5):
        p_k = service.update_mastery(p_k, is_correct=True)
    assert p_k > 0.90, f"Multiple correct answers should yield high mastery: {p_k}"

    # Multiple incorrect answers should decrease mastery towards lower bound
    for _ in range(5):
        p_k = service.update_mastery(p_k, is_correct=False)
    assert p_k < 0.35, f"Multiple incorrect answers should drive mastery down: {p_k}"


def test_bkt_display_formatting_and_bands():
    service = BKTMasteryService()
    assert service.format_display_percentage(0.756) == 76
    assert service.format_display_percentage(0.0) == 0
    assert service.format_display_percentage(1.0) == 100

    assert service.get_mastery_band(0.85) == "mastered"
    assert service.get_mastery_band(0.55) == "proficient"
    assert service.get_mastery_band(0.35) == "review_needed"


if __name__ == "__main__":
    test_bkt_initial_prior()
    test_bkt_correct_answer_increases_mastery()
    test_bkt_incorrect_answer_decreases_mastery()
    test_bkt_learning_transition_property()
    test_bkt_repeated_practice_convergence()
    test_bkt_display_formatting_and_bands()
    print("ALL 6 BKT UNIT TESTS PASSED!")

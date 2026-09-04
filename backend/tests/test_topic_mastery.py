"""
LumoraAI - Phase 3 Unit Tests: Topic Mastery Engine & Learner Knowledge Profile
Tests:
- Normalization (concept & topic with acronym preservation)
- Weighted aggregation formula (reliability weights + coverage blending)
- Evidence confidence heuristics (low, moderate, high)
- Mastery status classification & low-evidence protection
- Historical trend calculation (improving, declining, stable, insufficient_data)
- Empty workspace handling
- Strict workspace isolation
- End-to-end Learner Knowledge Profile generation
"""
import pytest
import asyncio
from backend.app.services.topic_mastery_engine import (
    TopicMasteryEngine,
    normalize_concept_name,
    normalize_topic_name,
)
from backend.app.services.learner_profile_service import LearnerProfileService
from backend.app.repositories.bkt import bkt_repo
from backend.app.repositories.topic_mastery import topic_mastery_repo
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.services.bkt_mastery import bkt_service


def test_normalization():
    assert normalize_concept_name("bfs traversal") == "BFS Traversal"
    assert normalize_concept_name("  BFS  traversal   ") == "BFS Traversal"
    assert normalize_concept_name("Page 1: Handshake Protocol") == "Handshake Protocol"
    assert normalize_concept_name("Unit - 2: TLS Record Protocol") == "TLS Record Protocol"
    assert normalize_concept_name("rsa key exchange") == "RSA Key Exchange"
    assert normalize_concept_name("hmac authentication") == "HMAC Authentication"
    
    assert normalize_topic_name("graphs & trees") == "Graphs & Trees"
    assert normalize_topic_name("  ssl protocols ") == "SSL Protocols"
    assert normalize_topic_name("tcp / ip networking") == "TCP / IP Networking"


def test_topic_mastery_weighted_aggregation():
    engine = TopicMasteryEngine()

    res_empty = engine.calculate_topic_mastery([], total_concept_count=5)
    assert res_empty["mastery_probability"] == 0.30
    assert res_empty["coverage_ratio"] == 0.0
    assert res_empty["confidence_level"] == "none"
    assert res_empty["mastery_status"] == "not_assessed"

    assessed_single = [
        {"concept": "BFS", "p_mastery": 0.85, "attempts_count": 1, "correct_count": 1}
    ]
    res_single = engine.calculate_topic_mastery(assessed_single, total_concept_count=5)
    assert res_single["coverage_ratio"] == 0.20
    assert 0.39 <= res_single["mastery_probability"] <= 0.43
    assert res_single["confidence_level"] == "low"
    assert res_single["mastery_status"] in {"developing", "low_evidence"}

    assessed_full = [
        {"concept": "BFS", "p_mastery": 0.85, "attempts_count": 8, "correct_count": 7},
        {"concept": "DFS", "p_mastery": 0.90, "attempts_count": 6, "correct_count": 5},
        {"concept": "Dijkstra", "p_mastery": 0.80, "attempts_count": 6, "correct_count": 5},
    ]
    res_full = engine.calculate_topic_mastery(assessed_full, total_concept_count=3)
    assert res_full["coverage_ratio"] == 1.0
    assert res_full["mastery_probability"] >= 0.80
    assert res_full["confidence_level"] == "high"
    assert res_full["mastery_status"] == "strong"


def test_confidence_and_status_heuristics():
    engine = TopicMasteryEngine()

    res_low = engine.calculate_topic_mastery(
        [{"concept": "QuickSort", "p_mastery": 0.90, "attempts_count": 2, "correct_count": 2}],
        total_concept_count=1,
    )
    assert res_low["confidence_level"] == "low"
    assert res_low["mastery_status"] == "low_evidence"

    res_gap = engine.calculate_topic_mastery(
        [
            {"concept": "RedBlackTree", "p_mastery": 0.15, "attempts_count": 5, "correct_count": 1},
            {"concept": "AVLTree", "p_mastery": 0.20, "attempts_count": 5, "correct_count": 1},
        ],
        total_concept_count=2,
    )
    assert res_gap["mastery_probability"] < 0.30
    assert res_gap["confidence_level"] in {"moderate", "high"}
    assert res_gap["mastery_status"] == "critical_gap"


@pytest.mark.asyncio
async def test_historical_trends():
    engine = TopicMasteryEngine()
    ws_id = "test_ws_trends"

    await bkt_repo.upsert_concept_mastery(
        workspace_id=ws_id,
        topic="Graphs",
        concept="BFS",
        p_mastery=0.40,
        is_correct=False,
        response_time_ms=5000,
    )

    t1 = await engine.recalculate_topic(ws_id, "Graphs")
    assert t1["trend"] == "insufficient_data"

    await topic_mastery_repo.record_snapshot(
        workspace_id=ws_id,
        entity_type="topic",
        entity_id="Graphs",
        mastery_probability=0.40,
        confidence_level="low",
    )

    await bkt_repo.upsert_concept_mastery(
        workspace_id=ws_id,
        topic="Graphs",
        concept="BFS",
        p_mastery=0.72,
        is_correct=True,
        response_time_ms=3000,
    )
    t2 = await engine.recalculate_topic(ws_id, "Graphs")
    assert t2["trend"] == "improving"


@pytest.mark.asyncio
async def test_empty_workspace_profile():
    service = LearnerProfileService()
    await workspace_repo.create(
        workspace_id="os_empty_test",
        name="Operating Systems Empty",
        goal="OS Prep",
    )

    profile = await service.get_learner_profile("os_empty_test")
    assert profile["status"] == "not_assessed"
    assert profile["overall"]["mastery_percentage"] == 0
    assert profile["overall"]["confidence"] == "none"
    assert len(profile["strongest_topics"]) == 0
    assert len(profile["weakest_topics"]) == 0
    assert len(profile["top_knowledge_gaps"]) == 0


@pytest.mark.asyncio
async def test_workspace_isolation():
    engine = TopicMasteryEngine()
    service = LearnerProfileService()

    ws_dsa = "ws_test_iso_dsa"
    ws_ssl = "ws_test_iso_ssl"

    await workspace_repo.create(workspace_id=ws_dsa, name="DSA Track", goal="Prep")
    await workspace_repo.create(workspace_id=ws_ssl, name="SSL Track", goal="Prep")

    await document_repo.create(
        workspace_id=ws_dsa,
        title="DSA Notes",
        filename="dsa.pdf",
        file_type="pdf",
        file_size=1024,
    )
    await document_repo.create(
        workspace_id=ws_ssl,
        title="SSL Notes",
        filename="ssl.pdf",
        file_type="pdf",
        file_size=1024,
    )

    await bkt_repo.upsert_concept_mastery(
        workspace_id=ws_dsa,
        topic="Algorithms",
        concept="Binary Search",
        p_mastery=0.85,
        is_correct=True,
    )
    await bkt_repo.upsert_concept_mastery(
        workspace_id=ws_ssl,
        topic="Cryptography",
        concept="Handshake Protocol",
        p_mastery=0.75,
        is_correct=True,
    )

    await engine.recalculate_all_workspace_topics(ws_dsa)
    await engine.recalculate_all_workspace_topics(ws_ssl)

    profile_dsa = await service.get_learner_profile(ws_dsa)
    profile_ssl = await service.get_learner_profile(ws_ssl)

    dsa_topic_names = [t["topic"] for t in profile_dsa["strongest_topics"] + profile_dsa["weakest_topics"]]
    assert "Algorithms" in dsa_topic_names
    assert "Cryptography" not in dsa_topic_names

    ssl_topic_names = [t["topic"] for t in profile_ssl["strongest_topics"] + profile_ssl["weakest_topics"]]
    assert "Cryptography" in ssl_topic_names
    assert "Algorithms" not in ssl_topic_names

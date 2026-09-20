import uuid
import pytest
from unittest.mock import AsyncMock, patch

from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.services.tutor import (
    tutor_service,
    _clean_tutor_response,
    _clean_citation_excerpt,
)
from backend.app.services.query_understanding import query_understanding_service
from backend.app.schemas.tutor import TutorResponse
from backend.app.ai.types import AIResponse, AIRequest


# ============================================================================
# 1. RESPONSE SANITIZATION & CLEANING TESTS
# ============================================================================

def test_clean_tutor_response_strips_prompt_leaks():
    dirty_text = (
        "--- SOURCE [1]: SSL-UNIT - 1.pdf (Page/Slide 5) ---\n"
        "[WORKSPACE SOURCES CONTEXT]:\n"
        "PEDAGOGICAL MODE: SIMPLIFICATION\n"
        "LEARNER QUESTION: Explain in simple terms\n"
        "Here is a simple explanation of the handshake: It is like two diplomats agreeing on a secret language.\n\n"
        "|---|---|\n"
        "The core takeaway is confidentiality."
    )
    cleaned = _clean_tutor_response(dirty_text)
    assert "--- SOURCE [1]" not in cleaned
    assert "[WORKSPACE SOURCES CONTEXT]" not in cleaned
    assert "PEDAGOGICAL MODE:" not in cleaned
    assert "LEARNER QUESTION:" not in cleaned
    assert "|---|---|" not in cleaned
    assert "Here is a simple explanation" in cleaned
    assert "The core takeaway is confidentiality." in cleaned


def test_clean_citation_excerpt_strips_table_noise():
    raw_chunk = (
        "| Parameter | Value |\n"
        "|---|---|\n"
        "| Protocol | TLS 1.3 |\n"
        "The Premaster Secret is 48 bytes long and securely exchanged via public key encryption."
    )
    clean_excerpt = _clean_citation_excerpt(raw_chunk)
    assert "|---|---|" not in clean_excerpt
    assert "|" not in clean_excerpt
    assert "Premaster Secret is 48 bytes long" in clean_excerpt


# ============================================================================
# 2. QUERY UNDERSTANDING & PEDAGOGICAL MODE TESTS
# ============================================================================

def test_pedagogical_mode_classification():
    qus = query_understanding_service
    assert qus.detect_pedagogical_mode("Explain the SSL Handshake Protocol", "SPECIFIC_CONCEPT") == "standard"
    assert qus.detect_pedagogical_mode("Explain it in simpler terms", "CONTEXTUAL_FOLLOWUP") == "simplify"
    assert qus.detect_pedagogical_mode("Explain simply for a beginner", "SPECIFIC_CONCEPT") == "simplify"
    assert qus.detect_pedagogical_mode("Give me a concrete example of this", "CONTEXTUAL_FOLLOWUP") == "example"
    assert qus.detect_pedagogical_mode("Show a step-by-step code example", "SPECIFIC_CONCEPT") == "example"
    assert qus.detect_pedagogical_mode("Why is this important?", "CONTEXTUAL_FOLLOWUP") == "why_importance"
    assert qus.detect_pedagogical_mode("What problem does this solve?", "SPECIFIC_CONCEPT") == "why_importance"
    assert qus.detect_pedagogical_mode("What are the important exam points?", "CONTEXTUAL_FOLLOWUP") == "exam_points"
    assert qus.detect_pedagogical_mode("What are the high-yield exam questions?", "SPECIFIC_CONCEPT") == "exam_points"
    assert qus.detect_pedagogical_mode("Compare Handshake and Record Protocol", "COMPARE_CONTRAST") == "compare"
    assert qus.detect_pedagogical_mode("Summarize this PDF", "DOCUMENT_SUMMARY") == "summary"
    assert qus.detect_pedagogical_mode("Explain page 7", "PAGE_REFERENCE") == "page_focus"
    assert qus.detect_pedagogical_mode("Summarize pages 5 to 8", "PAGE_RANGE_REFERENCE") == "page_range_focus"


# ============================================================================
# 3. FIXTURE: DEDICATED SSL WORKSPACE WITH REPRESENTATIVE KNOWLEDGE BASE
# ============================================================================

import pytest_asyncio

_shared_ssl_ws_id = None

@pytest_asyncio.fixture
async def ssl_workspace():
    global _shared_ssl_ws_id
    if _shared_ssl_ws_id is None:
        ws_id = f"ws_tutor_quality_{uuid.uuid4().hex[:8]}"
        await workspace_repo.create(
            workspace_id=ws_id,
            name="Network Security Track",
            goal="Master SSL/TLS Architecture and Network Security",
            level="advanced",
        )
        doc = await document_repo.create(
            workspace_id=ws_id,
            title="SSL Unit 1 - Security Protocols",
            filename="SSL-UNIT - 1.pdf",
            file_type="pdf",
            file_size=1548576,
            page_count=45,
            status="ready",
        )
        doc_id = str(doc["id"])
        chunks_data = [
            {
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "document_id": doc_id,
                "document_name": "SSL-UNIT - 1.pdf",
                "chunk_index": 1,
                "page_number": 1,
                "heading": "SSL Architecture Overview",
                "text": "1. SSL Handshake Protocol: Establishes a secure session between client and server by negotiating cipher suites, exchanging cryptographic random nonces, and authenticating server certificates.\n2. SSL Record Protocol: Provides confidentiality and data integrity using symmetric encryption and message authentication codes.\n3. Change Cipher Spec Protocol: Transitions the connection into newly negotiated cryptographic parameters.\n4. Alert Protocol: Transmits warning and fatal alert messages across peers.",
                "token_count": 80,
                "embedding": [0.05] * 768,
            },
            {
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "document_id": doc_id,
                "document_name": "SSL-UNIT - 1.pdf",
                "chunk_index": 2,
                "page_number": 5,
                "heading": "SSL Handshake Phase 1 & 2",
                "text": "Phase 1: Client Hello and Server Hello establish protocol version, cipher suite, and 32-byte nonces. Phase 2: Server sends digital certificate, ServerKeyExchange, and ServerHelloDone.",
                "token_count": 55,
                "embedding": [0.05] * 768,
            },
            {
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "document_id": doc_id,
                "document_name": "SSL-UNIT - 1.pdf",
                "chunk_index": 3,
                "page_number": 6,
                "heading": "SSL Handshake Phase 3 & 4",
                "text": "Phase 3: Client Key Exchange transfers the 48-byte Premaster Secret. Phase 4: Change Cipher Spec is exchanged and Finished message verifies handshake integrity.",
                "token_count": 50,
                "embedding": [0.05] * 768,
            },
            {
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "document_id": doc_id,
                "document_name": "SSL-UNIT - 1.pdf",
                "chunk_index": 4,
                "page_number": 7,
                "heading": "Premaster Secret and Master Secret Derivation",
                "text": "Page 7 details the cryptographic key derivation: Both client and server compute the 48-byte Master Secret using pseudorandom function PRF(Premaster Secret, 'master secret', client_random + server_random). Key material for AES-GCM encryption and HMAC authentication is derived from Master Secret.",
                "token_count": 65,
                "embedding": [0.05] * 768,
            },
            {
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "document_id": doc_id,
                "document_name": "SSL-UNIT - 1.pdf",
                "chunk_index": 5,
                "page_number": 8,
                "heading": "Record Protocol Architecture",
                "text": "Page 8: The Record Protocol fragments application data into blocks <= 16KB, applies optional compression, computes HMAC-SHA256, and encrypts with AES-GCM authenticated cipher.",
                "token_count": 50,
                "embedding": [0.05] * 768,
                "metadata": {"has_table": True},
            },
        ]
        await chunk_repo.insert_chunks(chunks_data)
        await document_repo.update_status(doc_id, "ready", page_count=45, chunk_count=len(chunks_data))
        _shared_ssl_ws_id = ws_id

    yield _shared_ssl_ws_id


# ============================================================================
# 4. END-TO-END PEDAGOGICAL TUTOR INTENT VERIFICATION
# ============================================================================

@pytest.mark.asyncio
async def test_tutor_basic_concept_teaching_flow(ssl_workspace: str):
    """
    1. Basic Concept Explanation:
    - Direct pedagogical answer
    - Citations attached and grounded
    - Appropriate follow-ups suggested
    """
    mock_ai_resp = AIResponse(
        content=(
            "### SSL Record Protocol\n\n"
            "**Definition & Intuition**: The SSL Record Protocol provides confidentiality and message integrity for application data transmitted over a secured channel.\n\n"
            "**Operational Mechanism**:\n"
            "1. **Fragmentation**: Large application messages are divided into blocks <= 16 KB.\n"
            "2. **Compression**: Optional lossless data compression is applied.\n"
            "3. **MAC Generation**: A Message Authentication Code is appended for integrity.\n"
            "4. **Encryption**: The payload is encrypted using the negotiated symmetric cipher.\n\n"
            "**Key Takeaway**: It secures transmitted data blocks once session keys have been established."
        ),
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=150.0,
        is_fallback=False,
    )

    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_ai_resp

        res = await tutor_service.answer_question(ssl_workspace, "What is the SSL Record Protocol?")

        assert res.retrieval.grounded is True
        assert len(res.citations) > 0
        assert res.retrieval.pedagogical_mode == "standard"
        assert res.retrieval.model_name == "models/gemini-3.8-flash"
        assert res.retrieval.is_fallback is False
        assert "SSL Record Protocol" in res.message.content
        assert "Fragmentation" in res.message.content
        assert len(res.suggested_follow_ups) == 3

        called_req: AIRequest = mock_gen.call_args[0][0]
        assert "PEDAGOGICAL DIRECTIVE: DIRECT TEACHING" in called_req.prompt


@pytest.mark.asyncio
async def test_tutor_explain_simply_directive(ssl_workspace: str):
    """
    2. Explain Simply / Beginner-Friendly:
    - Injects simplification directive (everyday analogy, plain language, no dense unexplained jargon)
    - Suggests next logical follow-ups (example, practical importance)
    """
    mock_ai_resp = AIResponse(
        content=(
            "Think of the SSL Handshake like two people meeting in a bank vault:\n\n"
            "1. First, they say hello and choose which language they both speak.\n"
            "2. Next, the bank proves its identity by showing an official government ID (digital certificate).\n"
            "3. Finally, they agree on a temporary secret code that only the two of them know.\n\n"
            "From that point onward, anyone eavesdropping will only hear gibberish."
        ),
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=140.0,
        is_fallback=False,
    )

    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_ai_resp

        res = await tutor_service.answer_question(ssl_workspace, "Explain the SSL Handshake in simple terms.")

        assert res.retrieval.grounded is True
        assert res.retrieval.pedagogical_mode == "simplify"
        called_req: AIRequest = mock_gen.call_args[0][0]
        assert "PEDAGOGICAL DIRECTIVE: SIMPLIFICATION" in called_req.prompt
        assert "Can you give me a concrete example?" in res.suggested_follow_ups


@pytest.mark.asyncio
async def test_tutor_concrete_example_directive(ssl_workspace: str):
    """
    3. Concrete Step-by-Step Example:
    - Injects step-by-step example directive
    - Breaks down inputs, transformation, and output
    """
    mock_ai_resp = AIResponse(
        content=(
            "### Concrete Step-by-Step Example: Master Secret Derivation\n\n"
            "**Step 1: Inputs**\n"
            "- 48-byte Premaster Secret\n"
            "- Client Random (32 bytes)\n"
            "- Server Random (32 bytes)\n\n"
            "**Step 2: Pseudorandom Function (PRF)**\n"
            "Both sides compute:\n"
            "`Master_Secret = PRF(Premaster_Secret, 'master secret', Client_Random + Server_Random)`\n\n"
            "**Step 3: Verification**\n"
            "Both peers independently derive the same 48-byte Master Secret to generate AES encryption keys."
        ),
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=130.0,
        is_fallback=False,
    )

    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_ai_resp

        res = await tutor_service.answer_question(ssl_workspace, "Give a concrete example of Master Secret derivation.")

        assert res.retrieval.grounded is True
        assert res.retrieval.pedagogical_mode == "example"
        called_req: AIRequest = mock_gen.call_args[0][0]
        assert "PEDAGOGICAL DIRECTIVE: CONCRETE STEP-BY-STEP EXAMPLE" in called_req.prompt
        assert "Explain this in simpler terms" in res.suggested_follow_ups


@pytest.mark.asyncio
async def test_tutor_why_importance_directive(ssl_workspace: str):
    """
    4. Architectural Motivation / Why It Matters:
    - Explains fundamental problem solved
    - Details what breaks or fails without it
    """
    mock_ai_resp = AIResponse(
        content=(
            "### Why the SSL Nonces (Random Values) Are Critical\n\n"
            "**Core Problem Solved**: Replay attacks.\n\n"
            "**Failure Mode Without It**: If client and server random values were omitted, an attacker on the same Wi-Fi could record an encrypted session and replay the exact packets later to authenticate without knowing the secret keys.\n\n"
            "**Architectural Significance**: Nonces guarantee session freshness and prevent attackers from decrypting replayed sessions."
        ),
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=120.0,
        is_fallback=False,
    )

    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_ai_resp

        res = await tutor_service.answer_question(ssl_workspace, "Why is the client and server random nonce important in SSL?")

        assert res.retrieval.grounded is True
        assert res.retrieval.pedagogical_mode == "why_importance"
        called_req: AIRequest = mock_gen.call_args[0][0]
        assert "PEDAGOGICAL DIRECTIVE: ARCHITECTURAL MOTIVATION & IMPORTANCE" in called_req.prompt


@pytest.mark.asyncio
async def test_tutor_compare_two_concepts(ssl_workspace: str):
    """
    5. Compare Two Concepts:
    - Structured side-by-side comparison (Purpose, Mechanism, Tradeoffs)
    """
    mock_ai_resp = AIResponse(
        content=(
            "### Comparison: SSL Handshake Protocol vs. SSL Record Protocol\n\n"
            "| Feature | SSL Handshake Protocol | SSL Record Protocol |\n"
            "| :--- | :--- | :--- |\n"
            "| **Purpose** | Session establishment & authentication | Data confidentiality & integrity |\n"
            "| **Cryptography** | Asymmetric (RSA/ECDHE) | Symmetric (AES-GCM / HMAC) |\n"
            "| **When Used** | Initial connection setup | Continuous application data transfer |\n"
            "| **Performance** | High computational cost | High throughput, low latency |"
        ),
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=160.0,
        is_fallback=False,
    )

    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_ai_resp

        res = await tutor_service.answer_question(ssl_workspace, "Compare the Handshake Protocol vs the Record Protocol.")

        assert res.retrieval.grounded is True
        assert res.retrieval.pedagogical_mode == "compare"
        called_req: AIRequest = mock_gen.call_args[0][0]
        assert "COMPARATIVE INSTRUCTION:" in called_req.prompt
        assert "PEDAGOGICAL DIRECTIVE: STRUCTURED COMPARISON" in called_req.prompt


@pytest.mark.asyncio
async def test_tutor_document_summary(ssl_workspace: str):
    """
    6. Document Summary:
    - Executive overview, key sections, and takeaways
    """
    mock_ai_resp = AIResponse(
        content=(
            "### Executive Summary: SSL-UNIT - 1\n\n"
            "**1. Core Focus**: Comprehensive coverage of Transport Layer Security and SSL protocol architecture.\n\n"
            "**2. Major Sub-Protocols Covered**:\n"
            "- **SSL Handshake Protocol**: Negotiates cipher suites and exchanges nonces.\n"
            "- **Change Cipher Spec Protocol**: Signals switch to newly negotiated cipher parameters.\n"
            "- **Alert Protocol**: Communicates fatal and warning error messages.\n"
            "- **Record Protocol**: Enforces confidentiality and integrity on data packets.\n\n"
            "**3. Key Takeaway**: Provides end-to-end security between client and server."
        ),
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=180.0,
        is_fallback=False,
    )

    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_ai_resp

        res = await tutor_service.answer_question(ssl_workspace, "Summarize this PDF.")

        assert res.retrieval.grounded is True
        assert res.retrieval.pedagogical_mode == "summary"
        called_req: AIRequest = mock_gen.call_args[0][0]
        assert "PEDAGOGICAL DIRECTIVE: STRUCTURED DOCUMENT SUMMARY" in called_req.prompt


@pytest.mark.asyncio
async def test_tutor_page_specific_focus(ssl_workspace: str):
    """
    7. Page-Specific Question (e.g. Page 7):
    - Confines explanation strictly to specified page
    - Exactly anchors citations to requested page
    """
    mock_ai_resp = AIResponse(
        content=(
            "Page 7 focuses on the derivation of cryptographic key material:\n"
            "It explains how the 48-byte Master Secret is computed using pseudorandom functions."
        ),
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=110.0,
        is_fallback=False,
    )

    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_ai_resp

        res = await tutor_service.answer_question(ssl_workspace, "Explain page 7 from the PDF.")

        assert res.retrieval.grounded is True
        assert res.retrieval.pedagogical_mode == "page_focus"
        assert len(res.citations) == 1
        assert res.citations[0].page_or_slide == 7
        called_req: AIRequest = mock_gen.call_args[0][0]
        assert "PAGE INSTRUCTION: The learner specifically asked about Page/Slide 7" in called_req.prompt


@pytest.mark.asyncio
async def test_tutor_page_range_focus(ssl_workspace: str):
    """
    8. Page-Range Question (e.g. Pages 5 to 8):
    - Synthesizes content across pages X..Y
    - Anchors citations across the range
    """
    mock_ai_resp = AIResponse(
        content="Pages 5 through 8 cover the complete handshake phases and the transition to the Record Protocol.",
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=120.0,
    )

    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_ai_resp

        res = await tutor_service.answer_question(ssl_workspace, "Summarize pages 5 to 8.")

        assert res.retrieval.grounded is True
        assert res.retrieval.pedagogical_mode == "page_range_focus"
        assert len(res.citations) >= 2
        assert all(5 <= c.page_or_slide <= 8 for c in res.citations)
        called_req: AIRequest = mock_gen.call_args[0][0]
        assert "PAGE RANGE INSTRUCTION:" in called_req.prompt


@pytest.mark.asyncio
async def test_tutor_followup_preserves_conversation_context(ssl_workspace: str):
    """
    9. Contextual Follow-Up:
    - Multi-turn conversation preserves antecedents
    """
    conv_id = f"conv_test_followup_{uuid.uuid4().hex[:6]}"

    mock_turn1 = AIResponse(
        content="1. **SSL Handshake Protocol**: The initial phase where client and server authenticate each other.",
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=100.0,
    )
    mock_turn2 = AIResponse(
        content="A concrete example of the SSL Handshake: Client sends ClientHello containing cipher suites and a 32-byte nonce.",
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=100.0,
    )

    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_turn1
        r1 = await tutor_service.answer_question(ssl_workspace, "Summarize the SSL architecture protocols", conversation_id=conv_id)
        assert r1.retrieval.grounded is True

        mock_gen.return_value = mock_turn2
        r2 = await tutor_service.answer_question(ssl_workspace, "Give me a concrete example of the first concept", conversation_id=conv_id)
        assert r2.retrieval.grounded is True
        assert r2.retrieval.pedagogical_mode == "example"
        called_req: AIRequest = mock_gen.call_args[0][0]
        assert "RECENT CONVERSATION HISTORY:" in called_req.prompt
        assert "CONTEXTUAL REFERENCE FOCUS:" in called_req.prompt


@pytest.mark.asyncio
async def test_tutor_exam_points_directive(ssl_workspace: str):
    """
    10. High-Yield Exam Points:
    - Injects exam preparation directive
    - Highlights frequent traps, definitions, and formulas
    """
    mock_ai_resp = AIResponse(
        content=(
            "### High-Yield Exam Points: SSL Protocols\n\n"
            "1. **Master Secret Size**: Always 48 bytes. (Frequent multiple choice question).\n"
            "2. **Nonce Purpose**: Replay attack mitigation; both client and server nonces are combined with the Premaster Secret.\n"
            "3. **Common Exam Trap**: The Change Cipher Spec is NOT part of the Handshake Protocol—it is an independent protocol with its own content type."
        ),
        provider="gemini",
        model="models/gemini-3.8-flash",
        latency_ms=130.0,
        is_fallback=False,
    )

    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_ai_resp

        res = await tutor_service.answer_question(ssl_workspace, "What are the important exam points for SSL?")

        assert res.retrieval.grounded is True
        assert res.retrieval.pedagogical_mode == "exam_points"
        called_req: AIRequest = mock_gen.call_args[0][0]
        assert "PEDAGOGICAL DIRECTIVE: HIGH-YIELD EXAM PREPARATION" in called_req.prompt


@pytest.mark.asyncio
async def test_tutor_unsupported_question_truthful_refusal(ssl_workspace: str):
    """
    11. Unsupported Content / Out of Domain:
    - Truthful refusal without hallucinating citations or facts
    - 0 citations returned
    - grounded = False
    """
    res = await tutor_service.answer_question(ssl_workspace, "How do you build a nuclear reactor in Minecraft?")
    assert res.retrieval.grounded is False
    assert len(res.citations) == 0
    assert "Your workspace sources do not contain enough information to answer that reliably." in res.message.content


@pytest.mark.asyncio
async def test_tutor_truthful_fallback_when_provider_unavailable(ssl_workspace: str):
    """
    12. Truthful Provider Fallback:
    - When AI Gateway fails or hits rate-limit cooldown
    - Returns structured pedagogical synthesis directly from verified sources
    - Never claims fallback is AI-generated
    - Citations preserved
    - is_fallback = True, model_name = 'source_fallback'
    """
    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception("HTTP 429 Rate limit cooldown active")

        res = await tutor_service.answer_question(ssl_workspace, "What is the Premaster Secret in SSL?")

        assert res.retrieval.grounded is True
        assert len(res.citations) > 0
        assert res.retrieval.is_fallback is True
        assert res.retrieval.model_name == "source_fallback"
        assert "⚠️ **AI Generation Model Temporarily Rate-Limited / Unavailable**" in res.message.content
        assert "without generative AI" in res.message.content
        assert "Premaster Secret" in res.message.content
        assert "|" not in res.message.content


@pytest.mark.asyncio
async def test_tutor_fallback_summary_is_structured_summary_not_raw_dump(ssl_workspace: str):
    """
    Regression Test 1 for FAILURE 1:
    - Summary fallback must be an actual multi-point structured summary, NOT raw excerpt concatenation.
    """
    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception("HTTP 429 Rate limit cooldown active")

        res = await tutor_service.answer_question(ssl_workspace, "Summarize the SSL architecture protocols")

        assert res.retrieval.grounded is True
        assert res.retrieval.is_fallback is True
        assert res.retrieval.model_name == "source_fallback"
        assert res.retrieval.pedagogical_mode == "summary"

        content = res.message.content
        # 1. Must be structured summary with executive overview and key topics
        assert "### Document Synthesis:" in content
        assert "**Executive Overview**:" in content
        assert "**Key Document Topics & Components**:" in content
        assert "**Core Synthesis Takeaway**:" in content
        assert "> **From SSL-UNIT" not in content  # No raw paragraph dump!
        # 2. Contains structured bullet points
        assert "- **" in content
        # 3. Preserves clean citations
        assert len(res.citations) > 0
        assert len(res.suggested_follow_ups) >= 2


@pytest.mark.asyncio
async def test_tutor_fallback_simplify_is_pedagogically_formatted(ssl_workspace: str):
    """
    Regression Test 2 for FAILURE 1:
    - Simplify fallback is pedagogically formatted with plain-terms definition and simple steps.
    """
    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception("HTTP 429 Rate limit cooldown active")

        res = await tutor_service.answer_question(ssl_workspace, "Explain the SSL Record Protocol simply for a beginner")

        assert res.retrieval.grounded is True
        assert res.retrieval.is_fallback is True
        assert res.retrieval.pedagogical_mode == "simplify"

        content = res.message.content
        assert "### Simplified Concept Overview:" in content
        assert "**Core Definition (In Plain Terms)**:" in content
        assert "**How It Works in Simple Steps**:" in content
        assert "1. **Foundation**:" in content
        assert "2. **Operation**:" in content
        assert "3. **Outcome**:" in content
        assert "**Key Takeaway**:" in content


@pytest.mark.asyncio
async def test_tutor_fallback_page_specific_excludes_unrelated_pages(ssl_workspace: str):
    """
    Regression Test 3 for FAILURE 1:
    - Page-specific fallback strictly anchors to requested page and excludes unrelated pages.
    """
    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception("HTTP 429 Rate limit cooldown active")

        res = await tutor_service.answer_question(ssl_workspace, "Explain the content on page 7")

        assert res.retrieval.grounded is True
        assert res.retrieval.is_fallback is True
        assert res.retrieval.pedagogical_mode == "page_focus"

        content = res.message.content
        assert "Page 7" in content
        assert "Restricted strictly to verified content from Page 7" in content
        for cit in res.citations:
            assert cit.page_or_slide == 7


@pytest.mark.asyncio
async def test_tutor_fallback_no_markdown_table_pipe_garbage_leaks(ssl_workspace: str):
    """
    Regression Test 4 for FAILURE 1:
    - No Markdown table-pipe garbage leaks into the learner-facing response.
    """
    with patch("backend.app.services.tutor.ai_gateway.generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception("HTTP 429 Rate limit cooldown active")

        # Chunk 5 on page 8 has table metadata and markdown table formatting
        res = await tutor_service.answer_question(ssl_workspace, "What is the Record Protocol architecture on page 8?")

        assert res.retrieval.grounded is True
        assert res.retrieval.is_fallback is True

        content = res.message.content
        assert "|" not in content
        assert "|---|---|" not in content
        assert "Record Protocol" in content



@pytest.mark.asyncio
async def test_tutor_ambiguous_document_clarification():
    """
    13. Ambiguous Document Clarification:
    - When user says 'Summarize this PDF' in a workspace with multiple documents
    - System asks for clarification and lists candidates
    """
    ws_id = f"ws_ambig_{uuid.uuid4().hex[:6]}"
    await workspace_repo.create(workspace_id=ws_id, name="Ambiguous Multi Doc", goal="Testing Ambiguity")
    try:
        await document_repo.create(workspace_id=ws_id, title="Doc 1", filename="algorithms.pdf", file_type="pdf", file_size=1000, page_count=10, status="ready")
        await document_repo.create(workspace_id=ws_id, title="Doc 2", filename="databases.pdf", file_type="pdf", file_size=1000, page_count=15, status="ready")

        res = await tutor_service.answer_question(ws_id, "Summarize this PDF.")
        assert res.retrieval.grounded is False
        assert len(res.citations) == 0
        assert "Which document would you like me to summarize" in res.message.content
        assert "algorithms.pdf" in res.message.content
        assert "databases.pdf" in res.message.content
    finally:
        await workspace_repo.delete(ws_id)


@pytest.mark.asyncio
async def test_tutor_empty_workspace_onboarding():
    """
    14. Empty Workspace Onboarding:
    - Queries in an empty workspace return clear onboarding guidance
    """
    ws_id = f"ws_empty_{uuid.uuid4().hex[:6]}"
    await workspace_repo.create(workspace_id=ws_id, name="Brand New Workspace", goal="Testing Empty")
    try:
        res = await tutor_service.answer_question(ws_id, "What sources are currently in this workspace?")
        assert res.retrieval.grounded is True
        assert len(res.citations) == 0
        assert "currently has no documents indexed" in res.message.content
        assert "Add Source" in res.message.content
    finally:
        await workspace_repo.delete(ws_id)


@pytest.mark.asyncio
async def test_zzz_cleanup_shared_ssl_workspace():
    global _shared_ssl_ws_id
    if _shared_ssl_ws_id:
        ws_id = _shared_ssl_ws_id
        _shared_ssl_ws_id = None
        await workspace_repo.delete(ws_id)


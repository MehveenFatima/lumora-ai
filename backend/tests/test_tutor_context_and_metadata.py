import asyncio
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.services.tutor import tutor_service


def assert_true(condition: bool, message: str):
    if not condition:
        print(f"[FAIL] {message}")
        sys.exit(1)
    print(f"  [OK] {message}")


async def run_tests():
    print("\n===============================================================")
    print("  LUMORAAI - TUTOR FOLLOW-UP CONTEXT & METADATA VERIFICATION")
    print("===============================================================\n")

    ws_id = "ws_test_context_and_meta"
    await workspace_repo.create(
        workspace_id=ws_id,
        name="Network Security Track",
        goal="Master SSL/TLS Architecture and Network Security",
        level="advanced",
    )

    # 1. Ingest a representative multi-page SSL document
    print("[STEP 1] Ingesting SSL-UNIT - 1 document into workspace...")
    doc = await document_repo.create(
        workspace_id=ws_id,
        title="SSL Unit 1 - Security Protocols",
        filename="SSL-UNIT - 1 (1).pdf",
        file_type="pdf",
        file_size=1548576,
        page_count=45,
        status="ready",
    )
    doc_id = str(doc["id"])

    # Ingest representative chunks across pages
    chunks_data = [
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "document_id": doc_id,
            "document_name": "SSL-UNIT - 1 (1).pdf",
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
            "document_name": "SSL-UNIT - 1 (1).pdf",
            "chunk_index": 2,
            "page_number": 6,
            "heading": "SSL Handshake Phases",
            "text": "Phase 1: Client Hello initiates negotiation with supported cipher suites and 32-byte client_random nonce. Server Hello responds with chosen cipher suite and server_random nonce.\nPhase 2: Server sends digital certificate and ServerKeyExchange.\nPhase 3: Client Key Exchange transfers the 48-byte Premaster Secret.",
            "token_count": 60,
            "embedding": [0.05] * 768,
        },
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "document_id": doc_id,
            "document_name": "SSL-UNIT - 1 (1).pdf",
            "chunk_index": 3,
            "page_number": 11,
            "heading": "Record Protocol & Symmetric Encryption",
            "text": "The SSL Record Protocol fragments application data into blocks <= 16KB, computes HMAC-SHA256 for integrity, and encrypts using AES-GCM or CBC mode symmetric encryption.",
            "token_count": 50,
            "embedding": [0.05] * 768,
        },
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "document_id": doc_id,
            "document_name": "SSL-UNIT - 1 (1).pdf",
            "chunk_index": 4,
            "page_number": 17,
            "heading": "Change Cipher Spec and Alert Handling",
            "text": "Change Cipher Spec consists of a single byte with value 1. The Alert Protocol signals session errors; fatal alerts immediately terminate the TCP session.",
            "token_count": 45,
            "embedding": [0.05] * 768,
        },
    ]

    await chunk_repo.insert_chunks(chunks_data)
    await document_repo.update_status(doc_id, "ready", page_count=45, chunk_count=len(chunks_data))

    # -------------------------------------------------------------
    # STEP 2: Test WORKSPACE_METADATA Queries
    # -------------------------------------------------------------
    print("\n[STEP 2] Testing WORKSPACE_METADATA queries...")
    meta_q1 = "What sources are currently in this workspace?"
    res_meta1 = await tutor_service.answer_question(ws_id, meta_q1)
    assert_true(res_meta1.retrieval.grounded is True, "Metadata query marked as grounded")
    assert_true("SSL-UNIT - 1 (1).pdf" in res_meta1.message.content, "Response lists SSL-UNIT - 1 (1).pdf")
    assert_true("45 pages" in res_meta1.message.content, "Response includes correct page count (45 pages)")
    assert_true(len(res_meta1.citations) == 0, "Metadata returns 0 citations (database inventory response)")

    meta_q2 = "How many documents are indexed?"
    res_meta2 = await tutor_service.answer_question(ws_id, meta_q2)
    assert_true("1 document" in res_meta2.message.content or "SSL-UNIT" in res_meta2.message.content, "Reports document count accurately")

    meta_q3 = "What topics are currently indexed?"
    res_meta3 = await tutor_service.answer_question(ws_id, meta_q3)
    assert_true(res_meta3.retrieval.grounded is True, "Topic metadata is grounded")
    assert_true("SSL-UNIT" in res_meta3.message.content, "Response displays workspace resources")

    # -------------------------------------------------------------
    # STEP 3: Multi-turn Contextual Conversation Test
    # -------------------------------------------------------------
    print("\n[STEP 3] Testing Multi-Turn Contextual Follow-Up Sequence...")
    conv_id = "conv_test_multi_turn_101"

    # Turn 1: Summarize this PDF
    print("  [Turn 1] User: 'Summarize this PDF.'")
    t1 = await tutor_service.answer_question(ws_id, "Summarize this PDF.", conversation_id=conv_id)
    assert_true(t1.retrieval.grounded is True, "Turn 1 summary recognized as grounded")
    assert_true(len(t1.citations) > 0, f"Turn 1 produced {len(t1.citations)} citations")

    # Turn 2: Explain the first concept in more detail
    print("\n  [Turn 2] User: 'Explain the first concept in more detail.'")
    t2 = await tutor_service.answer_question(ws_id, "Explain the first concept in more detail.", conversation_id=conv_id)
    assert_true(t2.retrieval.grounded is True, "Turn 2 follow-up recognized as grounded")
    assert_true(len(t2.citations) > 0, f"Turn 2 produced {len(t2.citations)} citations")
    assert_true("Handshake" in t2.message.content or "SSL" in t2.message.content, "Turn 2 explains resolved first concept (SSL Handshake Protocol)")

    # Turn 3: Give me a concrete example of that
    print("\n  [Turn 3] User: 'Give me a concrete example of that.'")
    t3 = await tutor_service.answer_question(ws_id, "Give me a concrete example of that.", conversation_id=conv_id)
    assert_true(t3.retrieval.grounded is True, "Turn 3 follow-up recognized as grounded")
    assert_true(len(t3.citations) > 0, f"Turn 3 produced {len(t3.citations)} citations")

    # Turn 4: Explain it in simpler terms
    print("\n  [Turn 4] User: 'Explain it in simpler terms.'")
    t4 = await tutor_service.answer_question(ws_id, "Explain it in simpler terms.", conversation_id=conv_id)
    assert_true(t4.retrieval.grounded is True, "Turn 4 follow-up recognized as grounded")
    assert_true(len(t4.citations) > 0, f"Turn 4 produced {len(t4.citations)} citations")

    # Turn 5: What are the important exam points from the concept we just discussed?
    print("\n  [Turn 5] User: 'What are the important exam points from the concept we just discussed?'")
    t5 = await tutor_service.answer_question(ws_id, "What are the important exam points from the concept we just discussed?", conversation_id=conv_id)
    assert_true(t5.retrieval.grounded is True, "Turn 5 exam points recognized as grounded")
    assert_true(len(t5.citations) > 0, f"Turn 5 produced {len(t5.citations)} citations")

    # -------------------------------------------------------------
    # STEP 4: Missing Information Refusal Test
    # -------------------------------------------------------------
    print("\n[STEP 4] Testing Out-of-Domain Refusal...")
    t_refuse = await tutor_service.answer_question(ws_id, "What does this PDF say about the architecture of the Roman Colosseum?")
    assert_true(t_refuse.retrieval.grounded is False, "Ungrounded query marked as ungrounded")
    assert_true(len(t_refuse.citations) == 0, "Refusal returned 0 citations")
    assert_true("do not contain enough information" in t_refuse.message.content, "Refusal contains standard honest refusal notice")

    # -------------------------------------------------------------
    # STEP 5: Cross-Workspace Isolation Test
    # -------------------------------------------------------------
    print("\n[STEP 5] Testing Cross-Workspace Isolation on Empty Workspace B...")
    ws_b_id = "ws_test_isolated_b"
    await workspace_repo.create(
        workspace_id=ws_b_id,
        name="Empty Workspace B",
        goal="Verify zero cross-workspace bleed",
    )
    t_b = await tutor_service.answer_question(ws_b_id, "Explain the first concept in more detail.")
    assert_true(t_b.retrieval.grounded is False, "Empty Workspace B cannot retrieve Workspace A concepts")
    assert_true(len(t_b.citations) == 0, "Empty Workspace B returns 0 citations")

    print("\n===============================================================")
    print("  ALL MULTI-TURN CONTEXT & METADATA TESTS PASSED SUCCESSFULLY!")
    print("===============================================================\n")


if __name__ == "__main__":
    asyncio.run(run_tests())

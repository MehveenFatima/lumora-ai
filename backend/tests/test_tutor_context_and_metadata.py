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
    print("  LUMORAAI - UNIFIED QUERY UNDERSTANDING & RAG VERIFICATION")
    print("===============================================================\n")

    ws_id = f"ws_test_unified_{int(uuid.uuid4().hex[:8], 16)}"
    await workspace_repo.create(
        workspace_id=ws_id,
        name="Network Security Track",
        goal="Master SSL/TLS Architecture and Network Security",
        level="advanced",
    )

    # 1. Ingest representative multi-page SSL document
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
            "document_name": "SSL-UNIT - 1 (1).pdf",
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
            "document_name": "SSL-UNIT - 1 (1).pdf",
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
            "document_name": "SSL-UNIT - 1 (1).pdf",
            "chunk_index": 5,
            "page_number": 8,
            "heading": "Record Protocol Architecture",
            "text": "Page 8: The Record Protocol fragments application data into blocks <= 16KB, applies optional compression, computes HMAC-SHA256, and encrypts with AES-GCM authenticated cipher.",
            "token_count": 50,
            "embedding": [0.05] * 768,
        },
    ]

    await chunk_repo.insert_chunks(chunks_data)
    await document_repo.update_status(doc_id, "ready", page_count=45, chunk_count=len(chunks_data))

    # -------------------------------------------------------------
    # TEST A — SUMMARY
    # -------------------------------------------------------------
    print("\n[TEST A] Summary Query ('Summarize this PDF.')")
    res_a = await tutor_service.answer_question(ws_id, "Summarize this PDF.")
    assert_true(res_a.retrieval.grounded is True, "Summary is grounded")
    assert_true(len(res_a.citations) > 0, f"Summary produced {len(res_a.citations)} citation(s)")

    # -------------------------------------------------------------
    # TEST B — FILENAME SUMMARY
    # -------------------------------------------------------------
    print("\n[TEST B] Filename Summary ('SSL-UNIT - 1 (1).pdf summarize it')")
    res_b = await tutor_service.answer_question(ws_id, "SSL-UNIT - 1 (1).pdf summarize it")
    assert_true(res_b.retrieval.grounded is True, "Filename summary is grounded")
    assert_true(len(res_b.citations) > 0, "Filename summary has citations")

    # -------------------------------------------------------------
    # TEST C — SPECIFIC FACT
    # -------------------------------------------------------------
    print("\n[TEST C] Specific Fact ('How is the Master Secret computed from the Premaster Secret?')")
    res_c = await tutor_service.answer_question(ws_id, "How is the Master Secret computed from the Premaster Secret?")
    assert_true(res_c.retrieval.grounded is True, "Specific fact is grounded")
    assert_true(any(c.page_or_slide == 7 for c in res_c.citations), "Citation points to Page 7")

    # -------------------------------------------------------------
    # TEST D — PAGE REFERENCE
    # -------------------------------------------------------------
    print("\n[TEST D] Page Reference ('Explain page 7 from the PDF.')")
    res_d = await tutor_service.answer_question(ws_id, "Explain page 7 from the PDF.")
    assert_true(res_d.retrieval.grounded is True, "Page 7 query is grounded")
    assert_true(len(res_d.citations) == 1 and res_d.citations[0].page_or_slide == 7, "Exact Page 7 citation generated")
    assert_true("Master Secret" in res_d.message.content or "Page 7" in res_d.message.content, "Page 7 content explained")

    # -------------------------------------------------------------
    # TEST E — PAGE RANGE REFERENCE
    # -------------------------------------------------------------
    print("\n[TEST E] Page Range Reference ('Summarize pages 5 to 8.')")
    res_e = await tutor_service.answer_question(ws_id, "Summarize pages 5 to 8.")
    assert_true(res_e.retrieval.grounded is True, "Page range is grounded")
    assert_true(len(res_e.citations) >= 2, f"Page range produced {len(res_e.citations)} citations across range")
    pages_cited = [c.page_or_slide for c in res_e.citations]
    assert_true(all(5 <= p <= 8 for p in pages_cited), f"All citations fall within 5..8 (got: {pages_cited})")

    # -------------------------------------------------------------
    # TEST F, G, H, I — MULTI-TURN FOLLOW-UP SEQUENCE
    # -------------------------------------------------------------
    print("\n[TEST F..I] Contextual Follow-Up Multi-Turn Sequence...")
    conv_id = f"conv_seq_{uuid.uuid4().hex[:6]}"
    
    # Q1: Summarize
    t1 = await tutor_service.answer_question(ws_id, "Summarize this PDF.", conversation_id=conv_id)
    assert_true(t1.retrieval.grounded is True, "Q1 summary grounded")

    # Q2: Explain the first concept in more detail
    t2 = await tutor_service.answer_question(ws_id, "Explain the first concept in more detail.", conversation_id=conv_id)
    assert_true(t2.retrieval.grounded is True, "Q2 first concept follow-up grounded")
    assert_true(len(t2.citations) > 0, "Q2 follow-up produced citations")
    assert_true("Handshake" in t2.message.content or "SSL" in t2.message.content, "Q2 explains Handshake Protocol")

    # Q3: Give me a concrete example of that
    t3 = await tutor_service.answer_question(ws_id, "Give me a concrete example of that.", conversation_id=conv_id)
    assert_true(t3.retrieval.grounded is True, "Q3 concrete example grounded")
    assert_true(len(t3.citations) > 0, "Q3 produced citations")

    # Q4: Explain it in simpler terms
    t4 = await tutor_service.answer_question(ws_id, "Explain it in simpler terms.", conversation_id=conv_id)
    assert_true(t4.retrieval.grounded is True, "Q4 simplification grounded")
    assert_true(len(t4.citations) > 0, "Q4 produced citations")

    # Q5: Exam points from what we just discussed
    t5 = await tutor_service.answer_question(ws_id, "What are the important exam points from what we just discussed?", conversation_id=conv_id)
    assert_true(t5.retrieval.grounded is True, "Q5 exam points grounded")
    assert_true(len(t5.citations) > 0, "Q5 produced citations")

    # -------------------------------------------------------------
    # TEST J, K, L — WORKSPACE METADATA
    # -------------------------------------------------------------
    print("\n[TEST J..L] Workspace Metadata Queries...")
    res_j = await tutor_service.answer_question(ws_id, "What sources are currently in this workspace?")
    assert_true(res_j.retrieval.grounded is True, "Metadata grounded")
    assert_true("SSL-UNIT - 1 (1).pdf" in res_j.message.content, "Source list includes SSL-UNIT - 1 (1).pdf")
    assert_true(len(res_j.citations) == 0, "Metadata returns 0 citations")

    res_k = await tutor_service.answer_question(ws_id, "How many documents are indexed?")
    assert_true("1 document" in res_k.message.content or "SSL-UNIT" in res_k.message.content, "Reports document count")

    res_l = await tutor_service.answer_question(ws_id, "What topics are currently indexed?")
    assert_true("Indexed Topics" in res_l.message.content or "SSL-UNIT" in res_l.message.content, "Topic inventory reported transparently")

    # -------------------------------------------------------------
    # TEST M — OUT OF RANGE PAGE
    # -------------------------------------------------------------
    print("\n[TEST M] Out of Range Page ('Explain page 100.')")
    res_m = await tutor_service.answer_question(ws_id, "Explain page 100.")
    assert_true(res_m.retrieval.grounded is False, "Out of range page marked ungrounded")
    assert_true("does not exist" in res_m.message.content and "45 pages" in res_m.message.content, "Returns transparent page limit notice")
    assert_true(len(res_m.citations) == 0, "Out of range page has 0 citations")

    # -------------------------------------------------------------
    # TEST N — OUT OF DOMAIN REFUSAL
    # -------------------------------------------------------------
    print("\n[TEST N] Out of Domain Refusal ('Roman Colosseum')")
    res_n = await tutor_service.answer_question(ws_id, "What does this PDF say about the architecture of the Roman Colosseum?")
    assert_true(res_n.retrieval.grounded is False, "Ungrounded query marked ungrounded")
    assert_true("do not contain enough information" in res_n.message.content, "Returns standard grounded refusal")
    assert_true(len(res_n.citations) == 0, "0 citations for ungrounded query")

    # -------------------------------------------------------------
    # TEST O — CROSS WORKSPACE ISOLATION
    # -------------------------------------------------------------
    print("\n[TEST O] Cross-Workspace Isolation on Empty Workspace B...")
    ws_b_id = f"ws_empty_b_{uuid.uuid4().hex[:6]}"
    await workspace_repo.create(workspace_id=ws_b_id, name="Empty B", goal="Isolation")
    res_o = await tutor_service.answer_question(ws_b_id, "How is the Master Secret computed?")
    assert_true(res_o.retrieval.grounded is False, "Empty Workspace B refused")
    assert_true(len(res_o.citations) == 0, "Workspace B returned 0 citations")

    # -------------------------------------------------------------
    # TEST P — UNRELATED DOCUMENT IN WORKSPACE C
    # -------------------------------------------------------------
    print("\n[TEST P] Different Document in Workspace C (Distributed Systems)...")
    ws_c_id = f"ws_c_{uuid.uuid4().hex[:6]}"
    await workspace_repo.create(workspace_id=ws_c_id, name="Distributed Systems Track", goal="Raft")
    doc_c = await document_repo.create(
        workspace_id=ws_c_id,
        title="Raft Consensus Paper",
        filename="raft_consensus.pdf",
        file_type="pdf",
        file_size=500000,
        page_count=12,
        status="ready",
    )
    await chunk_repo.insert_chunks([
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_c_id,
            "document_id": str(doc_c["id"]),
            "document_name": "raft_consensus.pdf",
            "chunk_index": 1,
            "page_number": 2,
            "heading": "Raft Leader Election",
            "text": "In Raft, if a follower receives no communication over an election timeout, it transitions to candidate state, increments term counter, and requests votes.",
            "token_count": 35,
            "embedding": [0.05] * 768,
        }
    ])
    res_p = await tutor_service.answer_question(ws_c_id, "How does leader election work in Raft?")
    assert_true(res_p.retrieval.grounded is True, "Workspace C query grounded in Raft paper")
    assert_true(res_p.citations[0].document_name == "raft_consensus.pdf", "Citation matches raft_consensus.pdf")
    assert_true(res_p.citations[0].page_or_slide == 2, "Citation points to Page 2 of Raft paper")

    # -------------------------------------------------------------
    # TEST Q — AMBIGUOUS MULTI-DOCUMENT WORKSPACE
    # -------------------------------------------------------------
    print("\n[TEST Q] Ambiguous Multi-Document Workspace ('Summarize this PDF' with 2 docs)")
    ws_multi_id = f"ws_multi_{uuid.uuid4().hex[:6]}"
    await workspace_repo.create(workspace_id=ws_multi_id, name="Multi Doc Track", goal="Testing Ambiguity")
    await document_repo.create(workspace_id=ws_multi_id, title="Doc 1", filename="algorithms.pdf", file_type="pdf", file_size=1000, page_count=10, status="ready")
    await document_repo.create(workspace_id=ws_multi_id, title="Doc 2", filename="databases.pdf", file_type="pdf", file_size=1000, page_count=15, status="ready")

    res_q = await tutor_service.answer_question(ws_multi_id, "Summarize this PDF.")
    assert_true(res_q.retrieval.grounded is False, "Ambiguous query prompts for clarification")
    assert_true("Which document would you like me to summarize" in res_q.message.content, "Prompt asks user to choose between algorithms.pdf and databases.pdf")

    print("\n===============================================================")
    print("  ALL 17 UNIFIED RAG TUTOR ACCEPTANCE TESTS PASSED!")
    print("===============================================================\n")


if __name__ == "__main__":
    asyncio.run(run_tests())

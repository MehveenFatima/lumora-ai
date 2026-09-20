import io
import uuid
import pytest
import pymupdf
import docx
import pptx
from typing import Dict, Any

from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.services.document_parser import document_parser
from backend.app.services.chunker import chunker_service
from backend.app.services.embeddings import embedding_service
from backend.app.services.retrieval import retrieval_service
from backend.app.services.tutor import tutor_service
from backend.app.services.query_understanding import query_understanding_service


def create_sample_academic_pdf() -> bytes:
    doc = pymupdf.open()

    p1 = doc.new_page()
    p1.insert_text(
        (50, 70),
        'Distributed Consensus and Fault Tolerance\n\n'
        'Fundamentals of Replication and Consistency\n\n'
        'State machine replication (SMR) ensures multiple nodes maintain identical state by executing deterministic commands in the exact same sequence. Under network partitions and asynchronous network delays, achieving consensus requires quorum agreements where a majority Q > N/2 participates.\n\n'
        'The CAP theorem states that a distributed data store can simultaneously provide at most two out of Consistency, Availability, and Partition tolerance.\n\n'
        'Figure 1: Replicated State Machine Architecture showing Consensus Module, Log, and State Machine.',
        fontsize=11,
    )

    p2 = doc.new_page()
    p2.insert_text(
        (50, 70),
        'Paxos vs Raft Consensus Mechanisms\n\n'
        'Comparing Classic Paxos and Leader-Driven Raft\n\n'
        'Classic Paxos operates in two phases: Prepare/Promise (Phase 1) and Propose/Accept (Phase 2). It achieves consensus without requiring a permanent designated leader, but requires multiple round-trip times and has high coordination complexity.\n\n'
        'In contrast, Raft decomposes consensus into three distinct subproblems: Leader Election, Log Replication, and Safety. Raft guarantees strong leader invariants where log entries flow strictly from leader to followers. A heartbeat mechanism with randomized election timeouts prevents split votes.\n\n'
        'Table 1: Consensus Algorithm Comparison\n'
        '| Algorithm | Leadership Model | Normal Latency | Failure Recovery |\n'
        '| Paxos | Symmetric / Multi-leader | 2 RTT | Complex |\n'
        '| Raft | Strong Single Leader | 1 RTT | Immediate |',
        fontsize=11,
    )

    p3 = doc.new_page()
    p3.insert_text(
        (50, 70),
        'Vector Clocks and Causality\n\n'
        'Event Ordering Without Synchronized Physical Clocks\n\n'
        'Lamport timestamps assign monotonic counters to establish a partial causal order. However, if L(a) < L(b), one cannot infer whether event a causally preceded event b or whether they are concurrent.\n\n'
        'Vector clocks resolve this limitation by assigning each node an array of integers representing causal progress. An event A causally precedes B if and only if all vector clock indices of A are <= B and at least one index is strictly smaller. Concurrent events exhibit incomparability in vector space.',
        fontsize=11,
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_sample_academic_docx() -> bytes:
    doc = docx.Document()
    doc.add_heading('Cloud Computing Architectures', level=1)
    doc.add_paragraph('Cloud virtualization abstracts hardware into elastic virtual machines and containers.')
    doc.add_heading('Microservices and Service Mesh', level=2)
    doc.add_paragraph('A service mesh manages service-to-service communication with mutual TLS and traffic splitting.')
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = 'Technology'
    table.rows[0].cells[1].text = 'Isolation Level'
    table.rows[1].cells[0].text = 'Containers'
    table.rows[1].cells[1].text = 'OS Namespace'

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def create_sample_academic_pptx() -> bytes:
    prs = pptx.Presentation()
    blank_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(blank_layout)
    slide.shapes.title.text = 'Microservice Resiliency Patterns'
    txBox = slide.shapes.add_textbox(pptx.util.Inches(1), pptx.util.Inches(2), pptx.util.Inches(5), pptx.util.Inches(2))
    tf = txBox.text_frame
    tf.text = 'Circuit Breakers prevent cascading failures when downstream microservices time out.'

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


@pytest.mark.asyncio
async def test_multi_format_parsers():
    # 1. PDF Parser
    pdf_bytes = create_sample_academic_pdf()
    pdf_pages = document_parser.parse(pdf_bytes, 'pdf')
    assert len(pdf_pages) == 3
    assert pdf_pages[0].page_number == 1
    assert 'Distributed Consensus' in pdf_pages[0].text
    assert pdf_pages[0].has_diagram is True
    assert len(pdf_pages[0].figure_captions) >= 1
    assert 'Vector Clocks' in pdf_pages[2].text

    png_bytes = document_parser.render_page_image(pdf_bytes, page_number=1)
    assert png_bytes is not None
    assert png_bytes.startswith(b'\x89PNG')

    # 2. DOCX Parser
    docx_bytes = create_sample_academic_docx()
    docx_pages = document_parser.parse(docx_bytes, 'docx')
    assert len(docx_pages) >= 1
    assert 'Cloud Computing Architectures' in docx_pages[0].text
    assert docx_pages[0].has_table is True

    # 3. PPTX Parser
    pptx_bytes = create_sample_academic_pptx()
    pptx_pages = document_parser.parse(pptx_bytes, 'pptx')
    assert len(pptx_pages) == 1
    assert pptx_pages[0].heading == 'Microservice Resiliency Patterns'
    assert 'Circuit Breakers' in pptx_pages[0].text


@pytest.mark.asyncio
async def test_new_workspace_ingestion_and_all_query_patterns():
    # 1. Create a NEW workspace
    new_ws_name = 'Distributed Systems & Cloud'
    ws_id = f"ws_dist_sys_{uuid.uuid4().hex[:8]}"
    ws = await workspace_repo.create(
        workspace_id=ws_id,
        name=new_ws_name,
        description='Advanced distributed algorithms, consensus, and fault tolerance.',
        goal='Master distributed state machines and consensus protocols',
        level='advanced',
        target_date='2026-12-31',
        daily_target_minutes=45,
        icon_name='Server',
    )

    # 2. Ingest New Academic PDF
    pdf_bytes = create_sample_academic_pdf()
    doc_record = await document_repo.create(
        workspace_id=ws_id,
        title='Distributed Consensus and Fault Tolerance',
        filename='Distributed_Consensus_and_Replication.pdf',
        file_type='pdf',
        file_size=len(pdf_bytes),
        status='uploading',
    )
    doc_id = doc_record['id']

    parsed_pages = document_parser.parse(pdf_bytes, 'pdf')
    assert len(parsed_pages) == 3

    chunks = chunker_service.chunk_pages(
        workspace_id=ws_id,
        document_id=doc_id,
        pages=parsed_pages,
        document_title='Distributed Consensus and Fault Tolerance',
        source_filename='Distributed_Consensus_and_Replication.pdf',
    )
    assert len(chunks) >= 3

    chunk_dicts = []
    for c in chunks:
        emb = await embedding_service.get_embedding(c.text)
        c_dict = c.to_dict()
        c_dict['embedding'] = emb
        c_dict['document_name'] = 'Distributed_Consensus_and_Replication.pdf'
        c_dict['document_title'] = 'Distributed Consensus and Fault Tolerance'
        chunk_dicts.append(c_dict)

    await chunk_repo.insert_chunks(chunk_dicts)
    await document_repo.update_status(
        doc_id,
        status='ready',
        page_count=len(parsed_pages),
        chunk_count=len(chunks),
        summary='Indexed distributed systems consensus curriculum',
    )
    await workspace_repo.increment_doc_count(ws_id, delta=1)

    paraphrased_query = 'How do replica nodes maintain synchronized state when network delays occur?'
    chunks_p, is_grounded_p, res_p = await retrieval_service.retrieve_relevant_chunks(
        workspace_id=ws_id,
        query=paraphrased_query,
    )
    assert is_grounded_p is True
    assert len(chunks_p) >= 1
    assert any('state machine replication' in c.text.lower() or 'consensus' in c.text.lower() for c in chunks_p)
    assert chunks_p[0].document_name == 'Distributed_Consensus_and_Replication.pdf'

    # Pattern B: Conversational Follow-Up With Pronouns
    mock_history = [
        {'role': 'user', 'content': 'Can you explain the Paxos algorithm?'},
        {
            'role': 'assistant',
            'content': 'Paxos is a distributed consensus protocol operating in Prepare/Promise and Propose/Accept phases.',
            'citations': [{'document_id': doc_id, 'document_name': 'Distributed_Consensus_and_Replication.pdf'}],
        },
    ]
    followup_query = 'What is its normal latency and phase structure?'
    chunks_f, is_grounded_f, res_f = await retrieval_service.retrieve_relevant_chunks(
        workspace_id=ws_id,
        query=followup_query,
        recent_history=mock_history,
    )
    assert is_grounded_f is True
    assert len(chunks_f) >= 1
    assert res_f.intent == 'CONTEXTUAL_FOLLOWUP'
    assert any('paxos' in c.text.lower() for c in chunks_f)

    # Pattern C: Page-Specific Question
    page_query = 'Explain page 3'
    chunks_pg, is_grounded_pg, res_pg = await retrieval_service.retrieve_relevant_chunks(
        workspace_id=ws_id,
        query=page_query,
    )
    assert is_grounded_pg is True
    assert res_pg.intent == 'PAGE_REFERENCE'
    assert res_pg.page_number == 3
    assert len(chunks_pg) >= 1
    assert chunks_pg[0].page_number == 3
    assert 'vector clocks' in chunks_pg[0].text.lower()

    # Pattern D: Document Summary Question
    summary_query = 'Summarize the main concepts in this document'
    chunks_s, is_grounded_s, res_s = await retrieval_service.retrieve_relevant_chunks(
        workspace_id=ws_id,
        query=summary_query,
    )
    assert is_grounded_s is True
    assert res_s.intent == 'DOCUMENT_SUMMARY'
    assert len(chunks_s) >= 1

    # Pattern E: Compare / Contrast Question
    compare_query = 'Compare Paxos and Raft'
    chunks_c, is_grounded_c, res_c = await retrieval_service.retrieve_relevant_chunks(
        workspace_id=ws_id,
        query=compare_query,
    )
    assert is_grounded_c is True
    assert res_c.intent == 'COMPARE_CONTRAST'
    assert len(chunks_c) >= 1
    all_text_c = ' '.join(c.text.lower() for c in chunks_c)
    assert 'paxos' in all_text_c and 'raft' in all_text_c

    # Pattern F: Table / Diagram Question
    table_query = 'What does Table 1 compare regarding consensus algorithms?'
    chunks_t, is_grounded_t, res_t = await retrieval_service.retrieve_relevant_chunks(
        workspace_id=ws_id,
        query=table_query,
    )
    assert is_grounded_t is True
    assert len(chunks_t) >= 1
    assert any('paxos' in c.text.lower() or 'raft' in c.text.lower() or 'consensus' in c.text.lower() for c in chunks_t)

    # Pattern G: Unsupported Question -> Truthful Refusal
    unsupported_query = 'How do I bake chocolate chip cookies from scratch?'
    chunks_u, is_grounded_u, res_u = await retrieval_service.retrieve_relevant_chunks(
        workspace_id=ws_id,
        query=unsupported_query,
    )
    assert is_grounded_u is False
    assert len(chunks_u) == 0

    tutor_res = await tutor_service.answer_question(
        workspace_id=ws_id,
        user_message=unsupported_query,
    )
    assert tutor_res.retrieval.grounded is False
    assert len(tutor_res.citations) == 0
    assert 'not contain enough information' in tutor_res.message.content.lower()

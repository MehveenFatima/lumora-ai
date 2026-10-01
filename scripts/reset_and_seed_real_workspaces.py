"""
LumoraAI - Database Reset and Real Workspace Seeding Script
============================================================
Seeds the four authentic course and RFC workspaces:
1. Operating Systems Architecture (xv6 Unix Kernel, MIT 6.1810)
2. Database Systems & Query Processing (CMU 15-445 Relational Model & Algebra)
3. Machine Learning Foundations (Stanford CS229 Supervised Learning & Regression)
4. Computer Networks — TCP (IETF RFC 9293 Transmission Control Protocol)

- Generates >= 20 validated MCQs per workspace in workspace_question_bank.
- Seeds >= 12 high-yield pedagogical flashcards per workspace.
- Seeds >= 5 grounded topics per workspace.
- Seeds >= 3 meaningful study plan milestones per workspace.
- Embeds with deterministic 768-dim embeddings (zero Gemini/OpenRouter API quota spent).
"""
import os
import sys
import json
import uuid
import asyncio
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())

from backend.app.db.connection import get_db_pool
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.quizzes import quiz_repo
from backend.app.repositories.secondary import flashcard_repo, study_plan_repo, activity_repo
from backend.app.repositories.bkt import bkt_repo
from backend.app.services.document_parser import document_parser
from backend.app.services.chunker import chunker_service
from backend.app.services.storage import storage_service
from backend.app.services.embeddings import OFFLINE_EMBEDDING_TAG, generate_deterministic_mock_embedding
from backend.app.services.question_generator import question_generator_service
from backend.app.services.topic_mastery_engine import topic_mastery_engine

WORKSPACES_CONFIG = [
    {
        "id": "ws_os_systems",
        "name": "Operating Systems Architecture",
        "goal": "Master Unix operating system kernel primitives, page tables, trap handling, and process scheduling.",
        "description": "Exploration of kernel design, memory virtualization, and hardware abstraction based on MIT 6.1810 / xv6.",
        "pdf_local": "backend/data/seed_pdfs/xv6_book_riscv.pdf",
        "doc_title": "xv6: a simple, Unix-like teaching operating system",
        "doc_filename": "xv6_book_riscv.pdf",
        "topics": [
            "Kernel Organization & Hardware Abstraction",
            "Virtual Memory & Page Tables",
            "Process Creation & Scheduling",
            "Traps, System Calls & Interrupts",
            "File Systems & Buffer Cache",
            "Concurrency & Locking Mechanics",
        ],
        "study_tasks": [
            {"title": "Examine Kernel Page Table Layout & Address Translation", "tag": "Virtual Memory", "estimatedMinutes": 30, "priority": "high", "completed": False, "scheduledFor": "today"},
            {"title": "Review Trap Handling Flow from User Mode to Kernel", "tag": "Traps & Interrupts", "estimatedMinutes": 25, "priority": "medium", "completed": True, "scheduledFor": "today"},
            {"title": "Analyze xv6 Process Scheduler and Context Switch Mechanics", "tag": "Scheduling", "estimatedMinutes": 35, "priority": "low", "completed": False, "scheduledFor": "this_week"},
        ],
    },
    {
        "id": "ws_db_systems",
        "name": "Database Systems & Query Processing",
        "goal": "Understand the relational model, relational algebra operations, keys, constraints, and declarative SQL execution.",
        "description": "Foundational database principles from CMU 15-445 covering data models, relational algebra (selection, projection, joins), and integrity constraints.",
        "pdf_local": "backend/data/seed_pdfs/cmu_15445_relational_model.pdf",
        "doc_title": "CMU 15-445/645 Database Systems — Lecture #01: Relational Model & Algebra",
        "doc_filename": "01-relationalmodel.pdf",
        "topics": [
            "Relational Model & Schema Architecture",
            "Integrity Constraints & Primary/Foreign Keys",
            "Relational Algebra: Selection & Projection",
            "Relational Algebra: Joins & Cartesian Products",
            "Relational Algebra: Set Operations (Union, Intersection)",
            "Declarative Queries vs Procedural Execution",
        ],
        "study_tasks": [
            {"title": "Master Formal Relational Algebra Operators (Selection vs Projection)", "tag": "Relational Algebra", "estimatedMinutes": 25, "priority": "high", "completed": False, "scheduledFor": "today"},
            {"title": "Verify Referential Integrity Constraints and Foreign Key Rules", "tag": "Integrity Constraints", "estimatedMinutes": 20, "priority": "medium", "completed": True, "scheduledFor": "today"},
            {"title": "Compare Procedural Execution Plans against Declarative SQL Specifications", "tag": "Query Processing", "estimatedMinutes": 30, "priority": "low", "completed": False, "scheduledFor": "this_week"},
        ],
    },
    {
        "id": "ws_machine_learning",
        "name": "Machine Learning Foundations",
        "goal": "Master supervised learning algorithms, gradient descent optimization, and regression models.",
        "description": "Mathematical principles of supervised machine learning and loss function minimization based on Stanford CS229.",
        "pdf_local": "backend/data/seed_pdfs/cs229_lecture1.pdf",
        "doc_title": "Stanford CS229: Supervised Learning & Linear Regression",
        "doc_filename": "cs229-notes1.pdf",
        "topics": [
            "Supervised Learning & Hypothesis Formulations",
            "Linear Regression & Mean Squared Error",
            "Batch Gradient Descent Optimization",
            "Stochastic Gradient Descent & Learning Rates",
            "The Normal Equations & Analytical Solutions",
            "Locally Weighted Regression & Model Fitting",
        ],
        "study_tasks": [
            {"title": "Derive Gradient Descent Parameter Update Rules for Least Squares", "tag": "Gradient Descent", "estimatedMinutes": 35, "priority": "high", "completed": False, "scheduledFor": "today"},
            {"title": "Compare Convergence Properties of Batch vs Stochastic Gradient Descent", "tag": "Optimization", "estimatedMinutes": 25, "priority": "medium", "completed": True, "scheduledFor": "today"},
            {"title": "Analyze Closed-Form Normal Equation Derivation and Matrix Inversion", "tag": "Analytical Solutions", "estimatedMinutes": 30, "priority": "low", "completed": False, "scheduledFor": "this_week"},
        ],
    },
    {
        "id": "ws_computer_networks",
        "name": "Computer Networks — TCP",
        "goal": "Master TCP transport layer reliability, three-way handshakes, sequence numbers, acknowledgements, flow control, and congestion control.",
        "description": "Authoritative IETF Standards Track specification of the Transmission Control Protocol (TCP) based on RFC 9293.",
        "pdf_local": "backend/data/seed_pdfs/rfc9293_tcp.pdf",
        "doc_title": "RFC 9293 — Transmission Control Protocol (TCP)",
        "doc_filename": "rfc9293.pdf",
        "topics": [
            "TCP Architecture & Transmission Primitives",
            "Segment Structure, Sequence & Acknowledgment Numbers",
            "Connection Establishment (Three-Way Handshake)",
            "Connection Termination & State Machine Transitions",
            "Retransmission Timeout (RTO) & Sliding Window Flow Control",
            "Congestion Control Mechanisms & Event Processing",
        ],
        "study_tasks": [
            {"title": "Trace TCP Three-Way Handshake State Transitions (SYN, SYN-ACK, ACK)", "tag": "Connection Management", "estimatedMinutes": 25, "priority": "high", "completed": False, "scheduledFor": "today"},
            {"title": "Analyze Sliding Window Advertisements and Receiver Buffer Management", "tag": "Flow Control", "estimatedMinutes": 30, "priority": "medium", "completed": True, "scheduledFor": "today"},
            {"title": "Examine Retransmission Timeout Calculation and Sequence Number Wrap-around", "tag": "Reliability", "estimatedMinutes": 35, "priority": "low", "completed": False, "scheduledFor": "this_week"},
        ],
    },
]

CURATED_FLASHCARDS = {
    "ws_os_systems": [
        ("What is a page table and what role does it play in xv6?", "A page table is the hardware-facing data structure that maps virtual addresses used by processes to physical memory addresses, providing strict process isolation.", "Virtual Memory & Page Tables", 15),
        ("Why does the kernel require a separate page table from user processes?", "A dedicated kernel page table allows the operating system to access physical devices and kernel text while preventing user programs from directly reading or modifying privileged memory.", "Kernel Organization & Hardware Abstraction", 18),
        ("Compare user mode and supervisor mode execution in RISC-V.", "User mode executes unprivileged application code with restricted instruction access, whereas supervisor mode allows the kernel to execute privileged instructions, configure page tables, and handle device interrupts.", "Kernel Organization & Hardware Abstraction", 12),
        ("Explain the purpose of the trapframe structure during a system call.", "The trapframe preserves user registers across a kernel trap so that after servicing the system call or interrupt, the kernel can restore user state exactly and resume process execution.", "Traps, System Calls & Interrupts", 32),
        ("How does the xv6 scheduler select a process to run on a CPU core?", "The scheduler loops through the process table, acquires the process lock, finds an entry with state RUNNABLE, switches context to that process, and releases the lock.", "Process Creation & Scheduling", 48),
        ("What is the consequence of holding a spinlock while calling sleep()?", "Calling sleep while holding a spinlock can cause a system deadlock because no other core can release the lock or wake the sleeping process while interrupts remain disabled.", "Concurrency & Locking Mechanics", 55),
        ("How does the xv6 buffer cache coordinate concurrent disk block access?", "The buffer cache maintains a fixed pool of in-memory block buffers protected by locks, ensuring only one kernel thread modifies a cached disk block at any time.", "File Systems & Buffer Cache", 71),
        ("What role does the write-ahead logging system serve in the xv6 file system?", "Logging guarantees crash consistency by recording all metadata and data block updates in a sequential on-disk log before committing them to their true file system locations.", "File Systems & Buffer Cache", 78),
        ("Distinguish between an inode and a directory entry in xv6.", "An inode stores file metadata, permissions, and disk block addresses, whereas a directory entry is merely a filename mapped to an inode number.", "File Systems & Buffer Cache", 84),
        ("What triggers a page fault in virtual memory management?", "A page fault occurs when a program accesses a virtual address for which the page table entry is either unmapped, invalid, or lacks the required read/write permissions.", "Virtual Memory & Page Tables", 24),
        ("Explain the mechanism of copy-on-write (COW) fork optimization.", "COW fork marks child and parent page table entries read-only; when either attempts to write, a page fault traps to the kernel, which allocates a private physical copy only upon modification.", "Virtual Memory & Page Tables", 27),
        ("Why must interrupt handling be disabled during critical spinlock acquisition?", "If interrupts were enabled, a timer or device interrupt handler on the same CPU could attempt to acquire the already-held spinlock, causing an immediate single-core deadlock.", "Concurrency & Locking Mechanics", 57),
    ],
    "ws_db_systems": [
        ("What is a relational data model and what role does it play in DBMS design?", "The relational model organizes data into relations (tables) composed of tuples (rows) and attributes (columns), separating logical representation from physical storage.", "Relational Model & Schema Architecture", 1),
        ("Distinguish between procedural and declarative query languages.", "Procedural languages specify how to retrieve data step-by-step, while declarative languages (like SQL) specify what data is needed, leaving execution strategy to the query optimizer.", "Declarative Queries vs Procedural Execution", 2),
        ("What is the primary key constraint and what invariant does it guarantee?", "A primary key uniquely identifies each tuple in a relation, enforcing non-nullability and preventing duplicate entity representations.", "Integrity Constraints & Primary/Foreign Keys", 2),
        ("Explain how a foreign key maintains referential integrity between tables.", "A foreign key specifies that attribute values in one relation must correspond to an existing primary key value in another relation, preventing orphan references.", "Integrity Constraints & Primary/Foreign Keys", 3),
        ("Define the relational algebra selection (σ) operation.", "Selection filters tuples from an input relation that satisfy a specified boolean predicate, producing a subset of rows without modifying the schema.", "Relational Algebra: Selection & Projection", 3),
        ("Define the relational algebra projection (π) operation.", "Projection filters attributes from an input relation, returning only the specified columns and eliminating any duplicate resulting tuples.", "Relational Algebra: Selection & Projection", 4),
        ("Compare relational union (∪) and intersection (∩) operations.", "Union combines all distinct tuples appearing in either relation, whereas intersection returns only tuples that exist in both relations; both require union-compatible schemas.", "Relational Algebra: Set Operations (Union, Intersection)", 4),
        ("What is a cross product (Cartesian product) in relational algebra?", "The cross product (R × S) pairs every tuple in relation R with every tuple in relation S, resulting in a relation with cardinality equal to |R| × |S|.", "Relational Algebra: Joins & Cartesian Products", 5),
        ("Explain the natural join (⋈) operation and how it simplifies cross products.", "A natural join combines tuples from two relations that have matching values across all identically named attributes, projecting out duplicate join columns.", "Relational Algebra: Joins & Cartesian Products", 5),
        ("What is physical data independence in database systems?", "Physical data independence ensures that application queries and logical schemas remain unaffected when physical storage layouts, indexes, or file structures change.", "Relational Model & Schema Architecture", 1),
        ("Explain the condition under which two relations are union-compatible.", "Two relations are union-compatible when they have the same number of attributes and corresponding attributes possess identical or compatible data domains.", "Relational Algebra: Set Operations (Union, Intersection)", 4),
        ("Why does the relational model disallow duplicate tuples in pure relations?", "In mathematical set theory underpinning relational algebra, a relation is defined as a set of tuples; duplicate elements do not exist in sets.", "Relational Model & Schema Architecture", 2),
    ],
    "ws_machine_learning": [
        ("What is supervised learning and what role does the training set play?", "Supervised learning algorithms learn a mapping from input features to output targets by observing a training set of labeled examples.", "Supervised Learning & Hypothesis Formulations", 2),
        ("Define the hypothesis function for multivariate linear regression.", "The hypothesis function h_θ(x) = θ^T x computes a weighted linear combination of input features parameterized by weight vector θ.", "Supervised Learning & Hypothesis Formulations", 3),
        ("What is the cost function (J(θ)) for ordinary least squares regression?", "The cost function measures half the sum of squared differences between hypothesis predictions and true training labels: J(θ) = 1/2 ∑ (h_θ(x^(i)) - y^(i))^2.", "Linear Regression & Mean Squared Error", 4),
        ("Explain the batch gradient descent parameter update rule.", "Batch gradient descent updates each parameter θ_j by subtracting the product of learning rate α and the gradient of J(θ) computed over all training examples.", "Batch Gradient Descent Optimization", 5),
        ("Compare batch gradient descent with stochastic gradient descent (SGD).", "Batch gradient descent examines the entire dataset on each step for smooth convergence, while SGD updates parameters after each individual example, providing faster iteration on massive datasets.", "Stochastic Gradient Descent & Learning Rates", 7),
        ("What happens if the learning rate α is chosen too large during gradient descent?", "An excessively large learning rate causes parameter updates to overshoot the minimum, leading to oscillation or divergence of the cost function J(θ).", "Batch Gradient Descent Optimization", 6),
        ("What are the Normal Equations and when are they applied in linear regression?", "The Normal Equations provide the closed-form analytical solution θ = (X^T X)^(-1) X^T y that directly minimizes the sum of squared errors without iterative optimization.", "The Normal Equations & Analytical Solutions", 11),
        ("What is the computational limitation of using the Normal Equations for large datasets?", "Computing (X^T X)^(-1) incurs an O(d^3) matrix inversion cost, making it computationally prohibitive when the number of features d is extremely large.", "The Normal Equations & Analytical Solutions", 12),
        ("Explain the core intuition of locally weighted linear regression (LWR).", "LWR weights training examples near the query point higher using an exponentially decaying kernel, fitting a local linear hypothesis tailored to the immediate neighborhood.", "Locally Weighted Regression & Model Fitting", 14),
        ("Compare parametric learning algorithms with non-parametric algorithms.", "Parametric algorithms fit a fixed number of parameters θ independent of training set size, while non-parametric algorithms retain the data in memory to make predictions.", "Locally Weighted Regression & Model Fitting", 15),
        ("Why is the mean squared error cost function convex for linear regression?", "The Hessian matrix of J(θ) is positive semi-definite (X^T X ≥ 0), guaranteeing that J(θ) has a single global minimum with no local optima.", "Linear Regression & Mean Squared Error", 9),
        ("Explain how feature scaling improves gradient descent convergence.", "Feature scaling normalizes feature ranges so cost function contours become spherical rather than elongated ellipses, allowing gradient descent to march directly toward the minimum.", "Batch Gradient Descent Optimization", 6),
    ],
    "ws_computer_networks": [
        ("What is TCP and what role does it serve in the Internet protocol suite?", "TCP is a connection-oriented, transport-layer protocol providing reliable, in-order, full-duplex byte-stream delivery between application endpoints over an unreliable IP network.", "TCP Architecture & Transmission Primitives", 5),
        ("Explain the purpose of sequence numbers in TCP segment headers.", "Sequence numbers assign a 32-bit counter to each transmitted byte, allowing the receiver to reassemble data in order, detect gaps, and eliminate duplicate segments.", "Segment Structure, Sequence & Acknowledgment Numbers", 14),
        ("How does the TCP cumulative acknowledgment mechanism function?", "A TCP acknowledgment number indicates the next expected sequence number, implicitly acknowledging that all preceding bytes have been received correctly.", "Segment Structure, Sequence & Acknowledgment Numbers", 16),
        ("Trace the three-way handshake used for TCP connection establishment.", "Client sends SYN with initial sequence number (ISN); server replies with SYN-ACK acknowledging client ISN and stating server ISN; client replies with ACK to establish connection.", "Connection Establishment (Three-Way Handshake)", 22),
        ("Explain why a four-step sequence is typically used to close a TCP connection.", "Because TCP is full-duplex, each direction must be closed independently: endpoint A sends FIN and receives ACK, then endpoint B sends FIN and receives ACK.", "Connection Termination & State Machine Transitions", 28),
        ("What is the purpose of the TIME-WAIT state in TCP connection termination?", "TIME-WAIT ensures the final ACK is reliably delivered to the remote peer and allows delayed segments from the old connection to dissipate before reusing port numbers.", "Connection Termination & State Machine Transitions", 31),
        ("Distinguish between TCP flow control and TCP congestion control.", "Flow control protects the receiving endpoint buffer using the advertised window, while congestion control protects intermediate network routers using the congestion window.", "Retransmission Timeout (RTO) & Sliding Window Flow Control", 38),
        ("How does the sliding window mechanism coordinate byte transmission?", "The sliding window defines the range of sequence numbers a sender may transmit before receiving an acknowledgment, dynamically sliding forward as ACKs arrive.", "Retransmission Timeout (RTO) & Sliding Window Flow Control", 40),
        ("Explain how Retransmission Timeout (RTO) is calculated in TCP.", "RTO is dynamically calculated from a smoothed round-trip time (SRTT) and round-trip variance (RTTVAR) to adapt to changing network latency conditions.", "Retransmission Timeout (RTO) & Sliding Window Flow Control", 45),
        ("What is the consequence of silly window syndrome in TCP data exchange?", "Silly window syndrome occurs when data is transmitted in tiny segments due to small advertised receiver windows, wasting bandwidth on header overhead.", "Retransmission Timeout (RTO) & Sliding Window Flow Control", 42),
        ("Explain the role of the SYN cookie mechanism in TCP security.", "SYN cookies encode connection state into the initial sequence number, allowing the server to defend against SYN flood denial-of-service attacks without allocating memory buffers.", "Connection Establishment (Three-Way Handshake)", 25),
        ("What triggers TCP fast retransmit before the retransmission timer expires?", "Receipt of three duplicate ACKs indicates that a specific segment was lost while subsequent segments arrived, triggering immediate retransmission without waiting for RTO.", "Congestion Control Mechanisms & Event Processing", 50),
    ],
}


async def reset_database(pool):
    """Removes only the sample workspaces (and their data) so they can be re-seeded.
    Other users' workspaces and all accounts are left untouched."""
    print("--- [1/6] Removing previous copies of the sample workspaces ---")
    sample_ids = [cfg["id"] for cfg in WORKSPACES_CONFIG]
    async with pool.acquire() as conn:
        tables = [
            r["table_name"]
            for r in await conn.fetch(
                """
                SELECT table_name FROM information_schema.columns
                WHERE table_schema = 'public' AND column_name = 'workspace_id'
                """
            )
        ]
        for t in tables:
            await conn.execute(f"DELETE FROM {t} WHERE workspace_id = ANY($1::text[]);", sample_ids)
        await conn.execute("DELETE FROM workspaces WHERE id = ANY($1::text[]);", sample_ids)
        print(f"Cleared sample workspaces: {', '.join(sample_ids)}")


async def ensure_owner(email: str, password: str, name: str) -> dict:
    from backend.app.core.security import hash_password
    from backend.app.repositories.users import user_repo

    user = await user_repo.get_by_email(email)
    if user:
        print(f"Using existing account {email} as owner.")
        return user
    user = await user_repo.create(email=email, name=name, password_hash=hash_password(password))
    print(f"Created demo account {email}.")
    return user


async def seed_workspaces(owner_email: str, owner_password: str, owner_name: str):
    pool = await get_db_pool()
    if not pool:
        print("Database connection pool unavailable.")
        return

    owner = await ensure_owner(owner_email, owner_password, owner_name)
    await reset_database(pool)

    report_data = []

    for ws_cfg in WORKSPACES_CONFIG:
        ws_id = ws_cfg["id"]
        ws_name = ws_cfg["name"]
        print(f"\n==================================================")
        print(f"Seeding Workspace: {ws_name} ({ws_id})")
        print(f"==================================================")

        # 1. Create Workspace
        await workspace_repo.create(
            name=ws_name,
            goal=ws_cfg["goal"],
            description=ws_cfg["description"],
            workspace_id=ws_id,
            owner_id=owner["id"],
        )

        # 2. Read and parse real PDF
        pdf_path = ws_cfg["pdf_local"]
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Missing seed PDF: {pdf_path}")

        with open(pdf_path, "rb") as f:
            file_bytes = f.read()
        file_size = len(file_bytes)

        parsed_pages = document_parser.parse(file_bytes, "pdf")
        page_count = len(parsed_pages)
        print(f"Parsed {page_count} real pages ({file_size/1024:.1f} KB) from {ws_cfg['doc_filename']}.")

        # 3. Create Document record
        doc_rec = await document_repo.create(
            workspace_id=ws_id,
            title=ws_cfg["doc_title"],
            filename=ws_cfg["doc_filename"],
            file_type="pdf",
            file_size=file_size,
            status="uploading",
        )
        doc_id = doc_rec["id"]

        # 4. Upload original PDF to storage
        storage_path = await storage_service.upload_file(
            workspace_id=ws_id,
            document_id=doc_id,
            filename=ws_cfg["doc_filename"],
            file_bytes=file_bytes,
            content_type="application/pdf",
        )

        # 5. Chunk pages into semantic chunks
        chunks = chunker_service.chunk_pages(
            workspace_id=ws_id,
            document_id=doc_id,
            pages=parsed_pages,
            document_title=ws_cfg["doc_title"],
            source_filename=ws_cfg["doc_filename"],
        )
        chunk_count = len(chunks)
        print(f"Created {chunk_count} semantic chunks across {page_count} pages.")

        # 6. Embed chunks deterministically (768 dimensions, zero network/quota)
        chunk_dicts = []
        for c in chunks:
            c_dict = c.to_dict()
            c_dict["embedding"] = generate_deterministic_mock_embedding(c.text, 768)
            c_dict["metadata"] = {**(c_dict.get("metadata") or {}), "embedding_model": OFFLINE_EMBEDDING_TAG}
            c_dict["document_name"] = ws_cfg["doc_filename"]
            c_dict["document_title"] = ws_cfg["doc_title"]
            chunk_dicts.append(c_dict)

        await chunk_repo.insert_chunks(chunk_dicts)

        summary_text = f"Indexed {chunk_count} semantic chunks across {page_count} pages from {ws_cfg['doc_filename']} for grounded RAG."
        await document_repo.update_status(
            doc_id,
            status="ready",
            page_count=page_count,
            chunk_count=chunk_count,
            storage_path=storage_path,
            summary=summary_text,
        )
        await workspace_repo.increment_doc_count(ws_id, delta=1)

        # 7. Seed >= 20 verified MCQs in workspace_question_bank
        print(f"Generating and quality-validating Question Bank (target >= 20 MCQs)...")
        seeded_q_count = 0
        seen_fps = set()
        step = max(1, chunk_count // 55)

        async def _bank(q):
            await quiz_repo.add_to_question_bank(
                workspace_id=ws_id,
                topic=q.topic,
                concept=q.concept,
                difficulty=q.difficulty,
                question_text=q.question_text,
                options=q.options,
                correct_option=q.correct_option,
                explanation=q.explanation,
                document_id=doc_id,
                page_number=q.page_number,
                source_excerpt=q.source_excerpt,
                citation_metadata={"document_name": ws_cfg["doc_filename"], "page_number": q.page_number},
                fingerprint=q.fingerprint,
                question_type=getattr(q, "question_type", "conceptual"),
                quality_score=getattr(q, "quality_score", 1.0),
            )

        # Prefer LLM-written questions when an AI provider is configured (they pass the same
        # quality checks); the template synthesiser below fills any remaining slots.
        from backend.app.ai.gateway import ai_gateway

        if any(p.is_configured() for p in ai_gateway.providers.values()):
            seen_texts = []
            for round_idx, diff in enumerate([1, 2, 3, 2, 1, 3, 2, 3]):
                if seeded_q_count >= 20:
                    break
                pool = await question_generator_service.generate_candidate_pool(
                    workspace_id=ws_id,
                    target_count=5,
                    excluded_fingerprints=seen_fps,
                    excluded_texts=seen_texts,
                    preferred_difficulty=diff,
                    chunks=chunk_dicts,
                )
                for q in pool:
                    if seeded_q_count >= 20 or q.fingerprint in seen_fps:
                        continue
                    seen_fps.add(q.fingerprint)
                    seen_texts.append(q.question_text)
                    await _bank(q)
                    seeded_q_count += 1
            print(f"AI-generated questions banked: {seeded_q_count}")

        for i in range(250):
            if seeded_q_count >= 20:
                break
            chunk_idx = (i * step) % chunk_count
            chunk_obj = chunk_dicts[chunk_idx]
            target_diff = 1 if (seeded_q_count % 3 == 0) else (2 if (seeded_q_count % 3 == 1) else 3)

            synth_q = question_generator_service._synthesize_diverse_question(
                chunk=chunk_obj,
                chunk_index=chunk_idx,
                iteration_seed=i * 11 + 5,
                target_difficulty=target_diff,
                excluded_texts=[],
            )
            if synth_q and synth_q.validate():
                fp = synth_q.fingerprint
                if fp not in seen_fps:
                    seen_fps.add(fp)
                    await _bank(synth_q)
                    seeded_q_count += 1

        bank_total = await quiz_repo.count_question_bank(ws_id)
        print(f"Question Bank seeded: {bank_total} validated questions for {ws_id}.")

        # 8. Seed Flashcards (12 rich pedagogical cards per workspace)
        print(f"Seeding Flashcard Deck (>= 12 cards)...")
        cards = []
        curated_list = CURATED_FLASHCARDS.get(ws_id, [])
        for c_idx, (front, back, concept, p_num) in enumerate(curated_list, 1):
            cards.append({
                "id": f"card_{ws_id}_{c_idx}",
                "workspace_id": ws_id,
                "front": front,
                "back": back,
                "concept": concept,
                "source_document": ws_cfg["doc_filename"],
                "source_page": p_num,
                "interval_days": 1,
                "last_reviewed": None,
                "created_at": datetime.now(timezone.utc),
            })
        await flashcard_repo.save_deck(ws_id, cards)
        print(f"Seeded {len(cards)} flashcards for {ws_id}.")

        # 9. Seed Topics and initial BKT concepts (>= 5 topics)
        print(f"Seeding Topics & Mastery Baselines...")
        for idx, t_name in enumerate(ws_cfg["topics"]):
            c_name = t_name.split("&")[0].strip() if "&" in t_name else t_name.split(":")[0].strip()
            p_init = 0.35 if idx > 1 else 0.75
            await bkt_repo.upsert_concept_and_gap(
                workspace_id=ws_id,
                topic=t_name,
                concept=c_name,
                p_mastery=p_init,
                is_correct=p_init >= 0.5,
                gap_priority=0.45 if p_init < 0.5 else 0.10,
                gap_status="developing" if p_init < 0.5 else "proficient",
                contributing_signals=["baseline_diagnostic"],
                recommended_action="practice_mcq" if p_init < 0.5 else "maintain_mastery",
                response_time_ms=1200,
                user_id="default_user",
            )

        await topic_mastery_engine.recalculate_all_workspace_topics(ws_id, "default_user")
        print(f"Seeded {len(ws_cfg['topics'])} topics and recalculated mastery.")

        # 10. Seed Study Plan (>= 3 milestones tied to topics)
        study_plan = {
            "workspace_id": ws_id,
            "daily_target_minutes": 45,
            "today_completed_minutes": 15,
            "weekly_target_minutes": 225,
            "week_completed_minutes": 45,
            "tasks": [
                {
                    "id": f"task_{ws_id}_{t_i+1}",
                    "title": t_data["title"],
                    "tag": t_data["tag"],
                    "estimatedMinutes": t_data["estimatedMinutes"],
                    "priority": t_data["priority"],
                    "completed": t_data["completed"],
                    "scheduledFor": t_data["scheduledFor"],
                }
                for t_i, t_data in enumerate(ws_cfg["study_tasks"])
            ],
        }
        await study_plan_repo.save_plan(study_plan)
        print(f"Seeded {len(ws_cfg['study_tasks'])} study plan milestones.")

        # 11. Seed Initial Activity Events (real current UTC timestamps)
        await activity_repo.add_activity(
            workspace_id=ws_id,
            event_type="source_added",
            title=f"Curriculum Indexed: {ws_cfg['doc_filename']}",
            description=f"Indexed {page_count} authentic pages ({chunk_count} semantic vectors) for grounded RAG.",
        )
        await activity_repo.add_activity(
            workspace_id=ws_id,
            event_type="roadmap_adapted",
            title="Curriculum Diagnostic Initialized",
            description=f"Formulated learning objectives and question bank ({bank_total} validated MCQs).",
        )

        report_data.append({
            "workspace_id": ws_id,
            "name": ws_name,
            "document": ws_cfg["doc_filename"],
            "pages": page_count,
            "chunks": chunk_count,
            "question_bank_mcqs": bank_total,
            "flashcards": len(cards),
            "topics": len(ws_cfg["topics"]),
            "study_tasks": len(ws_cfg["study_tasks"]),
        })

    print("\n==================================================")
    print("ALL 4 REAL WORKSPACES SEEDED SUCCESSFULLY")
    print("==================================================")
    for r in report_data:
        print(f"- [{r['workspace_id']}] {r['name']}: {r['document']} ({r['pages']} pages, {r['chunks']} chunks) | Question Bank: {r['question_bank_mcqs']} MCQs | Flashcards: {r['flashcards']} | Topics: {r['topics']} | Study Milestones: {r['study_tasks']}")


if __name__ == "__main__":
    import argparse
    import secrets

    parser = argparse.ArgumentParser(description="Seed the four sample workspaces for a demo account.")
    parser.add_argument("--email", default=os.environ.get("LUMORA_DEMO_EMAIL", "demo@lumora.local"))
    parser.add_argument("--password", default=os.environ.get("LUMORA_DEMO_PASSWORD"))
    parser.add_argument("--name", default="Demo Learner")
    args = parser.parse_args()
    password = args.password or secrets.token_urlsafe(12) + "9"
    asyncio.run(seed_workspaces(args.email, password, args.name))
    if not args.password:
        print(f"\nSign in as {args.email} with password: {password}  (only shown once; ignored if the account already existed)")

import asyncio
import re
from backend.app.db.connection import get_db_pool

# Workspaces that MUST NEVER BE DELETED
PRESERVED_WORKSPACE_IDS = {
    "dsa",
    "os",
    "ws_201621804547718",  # DBMS (presentation demo)
    "ws_238068824529423",  # Machine Learning (presentation demo)
    "ws_70120963497236",   # Custom SSl workspace (teacher upload: SSL-UNIT - 1.pdf)
    "ml",                  # Machine Learning & AI
    "aws",                 # AWS Solutions Architect
    "ws_dist_sys",         # Distributed Systems & Cloud
    "ws_19693464126604",   # ssl
    "ws_86631314916010",   # Quantum Computing Foundations
    "ws_24120198639335",   # SSl
    "ws_20497882130102",   # SSL
}

TEST_PATTERNS = [
    r"^ws_test_",
    r"^ws_lmp_",
    r"^ws_dist_sys_[a-f0-9]{8}$",
    r"^ws_empty_",
    r"^ws_multi_",
    r"^ws_c_",
    r"^ws_quiz_test_",
    r"^ws_debug_",
    r"^ws_smoke_",
    r"^os_empty_test$",
    r"^ws_tutor_quality_",
    r"^ws_ambig_",
]

def is_synthetic_test_workspace(ws_id: str) -> bool:
    if ws_id in PRESERVED_WORKSPACE_IDS:
        return False
    return any(re.search(pat, ws_id) for pat in TEST_PATTERNS)

async def run_cleanup():
    pool = await get_db_pool()
    if not pool:
        print("ERROR: Database connection unavailable!")
        return

    async with pool.acquire() as conn:
        all_ws = await conn.fetch("SELECT id, name FROM workspaces ORDER BY created_at ASC")
        print(f"Total workspaces before cleanup: {len(all_ws)}")

        to_delete = []
        to_preserve = []

        for ws in all_ws:
            ws_id = ws["id"]
            if ws_id in PRESERVED_WORKSPACE_IDS:
                to_preserve.append(ws)
            elif is_synthetic_test_workspace(ws_id):
                to_delete.append(ws)
            else:
                print(f"WARNING: Unknown workspace ID '{ws_id}' ('{ws['name']}'). Preserving for safety.")
                to_preserve.append(ws)

        print(f"\nWorkspaces to preserve ({len(to_preserve)}):")
        for ws in to_preserve:
            print(f"  - {ws['id']}: {ws['name']}")

        print(f"\nSynthetic test workspaces to delete ({len(to_delete)}):")
        for ws in to_delete:
            print(f"  - {ws['id']}: {ws['name']}")

        # Safety assertions
        for ws in to_delete:
            assert ws["id"] not in PRESERVED_WORKSPACE_IDS, f"CRITICAL: {ws['id']} is protected!"

        delete_ids = [ws["id"] for ws in to_delete]

        # Count affected documents and chunks before delete
        doc_count_before = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE workspace_id = ANY($1)", delete_ids
        )
        chunk_count_before = await conn.fetchval(
            "SELECT COUNT(*) FROM document_chunks WHERE workspace_id = ANY($1)", delete_ids
        )
        quiz_sessions_before = await conn.fetchval(
            "SELECT COUNT(*) FROM quiz_sessions WHERE workspace_id = ANY($1)", delete_ids
        )
        quiz_attempts_before = await conn.fetchval(
            "SELECT COUNT(*) FROM quiz_attempts WHERE workspace_id = ANY($1)", delete_ids
        )
        mastery_rows_before = await conn.fetchval(
            "SELECT COUNT(*) FROM learner_concept_mastery WHERE workspace_id = ANY($1)", delete_ids
        )

        print(f"\nRecords in test workspaces to be purged:")
        print(f"  - Documents: {doc_count_before}")
        print(f"  - Document Chunks: {chunk_count_before}")
        print(f"  - Quiz Sessions: {quiz_sessions_before}")
        print(f"  - Quiz Attempts: {quiz_attempts_before}")
        print(f"  - Mastery Records: {mastery_rows_before}")

        # Execute surgical delete in transaction
        async with conn.transaction():
            deleted_rows = await conn.execute(
                "DELETE FROM workspaces WHERE id = ANY($1)", delete_ids
            )
            print(f"\nExecute result: {deleted_rows}")

        # Verify post-cleanup state
        ws_after = await conn.fetch("SELECT id, name FROM workspaces ORDER BY created_at ASC")
        doc_total_after = await conn.fetchval("SELECT COUNT(*) FROM documents")
        chunk_total_after = await conn.fetchval("SELECT COUNT(*) FROM document_chunks")

        print(f"\n--- Post-Cleanup Verification ---")
        print(f"Total workspaces remaining: {len(ws_after)}")
        print(f"Total documents remaining: {doc_total_after}")
        print(f"Total chunks remaining: {chunk_total_after}")

        # Verify 0 orphaned records
        orphaned_docs = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE workspace_id NOT IN (SELECT id FROM workspaces)"
        )
        orphaned_chunks = await conn.fetchval(
            "SELECT COUNT(*) FROM document_chunks WHERE workspace_id NOT IN (SELECT id FROM workspaces)"
        )
        orphaned_quizzes = await conn.fetchval(
            "SELECT COUNT(*) FROM quiz_sessions WHERE workspace_id NOT IN (SELECT id FROM workspaces)"
        )
        print(f"Orphaned documents: {orphaned_docs}")
        print(f"Orphaned chunks: {orphaned_chunks}")
        print(f"Orphaned quizzes: {orphaned_quizzes}")

        assert orphaned_docs == 0
        assert orphaned_chunks == 0
        assert orphaned_quizzes == 0

        # Verify preserved workspaces are intact
        remaining_ids = {ws["id"] for ws in ws_after}
        for pid in PRESERVED_WORKSPACE_IDS:
            assert pid in remaining_ids, f"CRITICAL: Protected workspace {pid} was lost!"

        print("\nSUCCESS: All preserved workspaces intact and 0 orphaned records!")

if __name__ == "__main__":
    asyncio.run(run_cleanup())

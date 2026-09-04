import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.db.connection import get_db_pool

DSA_WORKSPACE_ID = "dsa"


async def cleanup_dsa_seed():
    print("\n===============================================================")
    print("  LUMORAAI — CLEANUP DSA DEMONSTRATION SEED DATA")
    print("===============================================================\n")

    docs = await document_repo.list_by_workspace(DSA_WORKSPACE_ID)
    cleaned_count = 0

    for doc in docs:
        meta = doc.get("metadata") or {}
        if meta.get("demo_seed") or meta.get("seed_type") == "presentation_demo" or doc["filename"].startswith("OpenDSA_"):
            doc_id = str(doc["id"])
            await chunk_repo.delete_by_document(doc_id)
            await document_repo.delete(doc_id)
            cleaned_count += 1
            print(f"  ✓ Removed seeded document: {doc['filename']} ({doc_id})")

    pool = await get_db_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE workspaces
                    SET document_count = (SELECT COUNT(*) FROM documents WHERE workspace_id = $1)
                    WHERE id = $1
                    """,
                    DSA_WORKSPACE_ID,
                )
        except Exception as e:
            print(f"Notice: {e}")

    print(f"\n🎉 Cleaned {cleaned_count} seeded demonstration records from '{DSA_WORKSPACE_ID}'. Genuine user records preserved.\n")


if __name__ == "__main__":
    asyncio.run(cleanup_dsa_seed())

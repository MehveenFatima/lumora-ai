"""
LumoraAI - Presentation Seeding Script (Original Supplied Materials Only)
Populates the authoritative presentation demonstration environment:
1. Phase 0 Health Check (:8000 direct and :3000 proxy)
2. Rule 3 Exact Name Lookup for the 4 presentation workspaces
3. Reads the ORIGINAL supplied learning-material PDFs from lumora_demo_content_pack/
4. Ingests all 12 original PDFs through the real backend ingestion pipeline
   (PyMuPDF text extraction, semantic chunking, Gemini 768-dim embeddings, Supabase Storage, PostgreSQL pgvector)
5. Strictly NO fabricated quiz attempts, mastery, knowledge gaps, or analytics
6. Fully idempotent and verifiable via PostgreSQL & API
"""

import os
import sys
import json
import zipfile
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
import asyncpg

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings

FASTAPI_URL = "http://127.0.0.1:8000"
PROXY_URL = "http://localhost:3000"

DEMO_CONTENT_DIR = PROJECT_ROOT / "lumora_demo_content_pack"
FALLBACK_ZIP_PATH = Path(r"C:\Users\ABDUL RAHMAN\Downloads\LumoraAI_Presentation_Demo_Content.zip")

# Authoritative Subject Configurations mapping to original PDF files
PRESENTATION_SUBJECTS = [
    {
        "name": "Data Structures & Algorithms",
        "description": "Comprehensive study of linear structures, balanced search trees, heaps, and graph algorithms.",
        "goal": "Master technical interview data structures and algorithmic complexity analysis",
        "level": "intermediate",
        "icon_name": "Layers",
        "folder": "01_Data_Structures_Algorithms",
        "docs": [
            {
                "filename": "DSA_Arrays_and_Hashing.pdf",
                "title": "DSA - Arrays and Hashing",
            },
            {
                "filename": "DSA_Trees_BST_and_Heaps.pdf",
                "title": "DSA - Trees, BST, and Heaps",
            },
            {
                "filename": "DSA_Graph_Traversal_and_Shortest_Path.pdf",
                "title": "DSA - Graph Traversal and Shortest Path",
            },
        ],
    },
    {
        "name": "Operating Systems",
        "description": "Deep dive into CPU scheduling, threads, concurrency, paging, and virtual memory.",
        "goal": "Understand OS kernels, process management, and virtual memory systems",
        "level": "intermediate",
        "icon_name": "Cpu",
        "folder": "02_Operating_Systems",
        "docs": [
            {
                "filename": "OS_Processes_and_Threads.pdf",
                "title": "OS - Processes and Threads",
            },
            {
                "filename": "OS_CPU_Scheduling.pdf",
                "title": "OS - CPU Scheduling",
            },
            {
                "filename": "OS_Virtual_Memory_and_Paging.pdf",
                "title": "OS - Virtual Memory and Paging",
            },
        ],
    },
    {
        "name": "DBMS",
        "description": "Relational database concepts, normalization, transactions, ACID properties, and B-Tree indexing.",
        "goal": "Master relational schema design, query optimization, and transaction concurrency",
        "level": "intermediate",
        "icon_name": "Database",
        "folder": "03_DBMS",
        "docs": [
            {
                "filename": "DBMS_SQL_and_Keys.pdf",
                "title": "DBMS - SQL and Keys",
            },
            {
                "filename": "DBMS_Normalization.pdf",
                "title": "DBMS - Normalization",
            },
            {
                "filename": "DBMS_Transactions_Indexing.pdf",
                "title": "DBMS - Transactions and Indexing",
            },
        ],
    },
    {
        "name": "Machine Learning",
        "description": "Foundational ML theory, regression, classification metrics, tree ensembles, and validation.",
        "goal": "Master core machine learning algorithms and statistical evaluation frameworks",
        "level": "intermediate",
        "icon_name": "Brain",
        "folder": "04_Machine_Learning",
        "docs": [
            {
                "filename": "ML_Regression_Fundamentals.pdf",
                "title": "ML - Regression Fundamentals",
            },
            {
                "filename": "ML_Classification_and_Metrics.pdf",
                "title": "ML - Classification and Metrics",
            },
            {
                "filename": "ML_Trees_Ensembles_and_Validation.pdf",
                "title": "ML - Trees, Ensembles, and Validation",
            },
        ],
    },
]


def ensure_demo_content_extracted():
    """Ensures the original supplied PDF files exist on disk."""
    if not DEMO_CONTENT_DIR.exists() or not any(DEMO_CONTENT_DIR.glob("**/*.pdf")):
        if FALLBACK_ZIP_PATH.exists():
            print(f"[EXTRACT] Unpacking original demo content from {FALLBACK_ZIP_PATH}...")
            with zipfile.ZipFile(FALLBACK_ZIP_PATH, "r") as z:
                z.extractall(PROJECT_ROOT)
            print("[EXTRACT] Content successfully unpacked.")
        else:
            raise FileNotFoundError(
                f"Supplied demo content pack not found at {DEMO_CONTENT_DIR} or {FALLBACK_ZIP_PATH}"
            )


async def check_health():
    """Phase 0 Diagnostic Check."""
    print("\n--- PHASE 0: Health Check ---")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. FastAPI Direct
        try:
            r = await client.get(f"{FASTAPI_URL}/api/v1/health")
            print(f"[FastAPI Direct :8000] Status: {r.status_code}")
            if r.status_code == 200:
                h = r.json()
                print(f"  Backend: {h.get('backend')}, Database: {h.get('database', {}).get('status')}, Vector: {h.get('vector', {}).get('capability')}")
            else:
                print(f"  Warning: FastAPI health returned HTTP {r.status_code}")
        except Exception as e:
            print(f"  Error connecting to FastAPI at {FASTAPI_URL}: {e}")
            raise SystemExit("FastAPI backend must be running on port 8000 before seeding.")

        # 2. Next.js Proxy
        try:
            r = await client.get(f"{PROXY_URL}/api/v1/health")
            print(f"[Next.js Proxy :3000] Status: {r.status_code}")
        except Exception as e:
            print(f"  Note: Next.js proxy on :3000 is not reachable ({e}). Direct FastAPI will be used.")


async def resolve_or_create_workspace(client: httpx.AsyncClient, subject: Dict[str, Any]) -> str:
    """
    Rule 3 Exact Name Lookup:
    - exactly 1 matching row -> use its real database ID
    - 0 rows -> create the workspace, then use the returned real ID
    - >1 rows -> raise Conflict and abort
    """
    name = subject["name"]
    res = await client.get(f"{FASTAPI_URL}/api/v1/workspaces", params={"name": name})
    if res.status_code != 200:
        raise RuntimeError(f"Failed to query workspaces: HTTP {res.status_code} - {res.text}")

    data = res.json()
    matches = [w for w in data.get("workspaces", []) if w["name"] == name]

    if len(matches) == 1:
        ws_id = matches[0]["id"]
        print(f"  Found existing workspace: '{name}' -> Database ID: {ws_id}")
        return ws_id
    elif len(matches) == 0:
        print(f"  Creating workspace: '{name}'...")
        payload = {
            "name": name,
            "description": subject["description"],
            "goal": subject["goal"],
            "level": subject["level"],
            "target_date": "2026-12-31",
            "daily_target_minutes": 45,
            "icon_name": subject["icon_name"],
        }
        create_res = await client.post(f"{FASTAPI_URL}/api/v1/workspaces", json=payload)
        if create_res.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create workspace '{name}': {create_res.status_code} - {create_res.text}")
        ws_id = create_res.json()["id"]
        print(f"  Created workspace: '{name}' -> Database ID: {ws_id}")
        return ws_id
    else:
        raise RuntimeError(f"Conflict: Found {len(matches)} workspaces matching exact name '{name}'. Aborting per Rule 3.")


async def upload_documents(client: httpx.AsyncClient, workspace_id: str, subject: Dict[str, Any]):
    """Uploads the original supplied PDFs through the real ingestion pipeline idempotently."""
    r = await client.get(f"{FASTAPI_URL}/api/v1/workspaces/{workspace_id}/documents")
    existing_filenames = set()
    if r.status_code == 200:
        docs = r.json().get("documents", [])
        existing_filenames = {d["filename"] for d in docs}

    folder_path = DEMO_CONTENT_DIR / subject["folder"]

    for doc_info in subject["docs"]:
        fn = doc_info["filename"]
        pdf_path = folder_path / fn

        if not pdf_path.exists():
            raise FileNotFoundError(f"Original supplied PDF not found: {pdf_path}")

        if fn in existing_filenames:
            print(f"    [EXISTS] Document '{fn}' already ingested. Skipping upload.")
            continue

        print(f"    [INGESTING] Uploading original PDF '{fn}' ({pdf_path.stat().st_size} bytes)...")
        with open(pdf_path, "rb") as f:
            files = {"file": (fn, f, "application/pdf")}
            data = {"title": doc_info["title"]}
            up_res = await client.post(
                f"{FASTAPI_URL}/api/v1/workspaces/{workspace_id}/documents",
                files=files,
                data=data,
                timeout=120.0,  # Allow time for text parsing and Gemini vector embedding
            )
            if up_res.status_code in (200, 201):
                doc_id = up_res.json().get("id")
                chunks_count = up_res.json().get("chunks_count", 0)
                print(f"    [SUCCESS] Ingested '{fn}' -> Doc ID: {doc_id}, Chunks: {chunks_count}")
            else:
                raise RuntimeError(f"Failed uploading '{fn}': HTTP {up_res.status_code} - {up_res.text}")


async def verify_database_state(workspace_ids: Dict[str, str]):
    """Direct PostgreSQL Verification."""
    print("\n====================================================")
    print("      POSTGRESQL DIRECT DATABASE VERIFICATION       ")
    print("====================================================")

    conn = await asyncpg.connect(settings.database_url)
    try:
        # 1. Total counts
        total_docs = await conn.fetchval("SELECT count(*) FROM documents")
        total_chunks = await conn.fetchval("SELECT count(*) FROM document_chunks")
        print(f"Database Totals: {total_docs} Documents, {total_chunks} Chunks")

        # 2. Workspace breakdown
        print("\nBreakdown by Presentation Workspace:")
        for name, ws_id in workspace_ids.items():
            doc_rows = await conn.fetch(
                "SELECT id, filename, chunk_count, status FROM documents WHERE workspace_id = $1 ORDER BY filename",
                ws_id
            )
            chunk_rows = await conn.fetch(
                "SELECT count(*) as count, count(embedding) as emb_count FROM document_chunks WHERE workspace_id = $1",
                ws_id
            )
            total_ws_chunks = chunk_rows[0]["count"]
            total_ws_embs = chunk_rows[0]["emb_count"]

            print(f"\n  Workspace: '{name}' (ID: {ws_id})")
            print(f"    Documents count: {len(doc_rows)}")
            print(f"    Chunks count: {total_ws_chunks}")
            print(f"    Embeddings count: {total_ws_embs}")

            for d in doc_rows:
                print(f"      - {d['filename']}: status={d['status']}, chunks={d['chunk_count']}")

        # 3. Vector embedding dimension verification
        dim_row = await conn.fetchrow("""
            SELECT atttypmod
            FROM pg_attribute
            WHERE attrelid = 'document_chunks'::regclass AND attname = 'embedding'
        """)
        dim = dim_row["atttypmod"] if dim_row else None
        print(f"\npgvector Embedding Column Dimension: vector({dim})")

    finally:
        await conn.close()


async def verify_api_endpoints(workspace_ids: Dict[str, str]):
    """Verifies backend API and proxy endpoints."""
    print("\n====================================================")
    print("           API ENDPOINTS VERIFICATION               ")
    print("====================================================")

    async with httpx.AsyncClient(timeout=15.0) as client:
        # GET /api/v1/workspaces
        r = await client.get(f"{FASTAPI_URL}/api/v1/workspaces")
        print(f"GET {FASTAPI_URL}/api/v1/workspaces -> HTTP {r.status_code}")
        data = r.json()
        all_workspaces = data.get("workspaces", [])
        print(f"Total workspaces returned: {len(all_workspaces)}")

        for name, ws_id in workspace_ids.items():
            r_docs = await client.get(f"{FASTAPI_URL}/api/v1/workspaces/{ws_id}/documents")
            print(f"GET {FASTAPI_URL}/api/v1/workspaces/{ws_id}/documents -> HTTP {r_docs.status_code} ({len(r_docs.json().get('documents', []))} docs)")

        # Proxy check if available
        try:
            r_proxy = await client.get(f"{PROXY_URL}/api/v1/workspaces")
            print(f"GET {PROXY_URL}/api/v1/workspaces -> HTTP {r_proxy.status_code}")
        except Exception:
            print(f"[NOTE] Next.js frontend proxy ({PROXY_URL}) is currently offline; direct backend verified.")


async def main():
    print("====================================================")
    print(" LumoraAI Real Presentation Data Seeding (Original) ")
    print("====================================================")

    ensure_demo_content_extracted()
    await check_health()

    resolved_workspace_ids = {}

    async with httpx.AsyncClient(timeout=180.0) as client:
        print("\n--- Resolving Workspaces & Ingesting Original Materials ---")
        for subject in PRESENTATION_SUBJECTS:
            name = subject["name"]
            print(f"\nProcessing Workspace: '{name}'...")

            # Rule 3 Workspace Resolution
            ws_id = await resolve_or_create_workspace(client, subject)
            resolved_workspace_ids[name] = ws_id

            # Upload 3 original supplied PDFs
            await upload_documents(client, ws_id, subject)

    # Verification
    await verify_database_state(resolved_workspace_ids)
    await verify_api_endpoints(resolved_workspace_ids)

    print("\n====================================================")
    print(" Presentation Seeding Completed Successfully!       ")
    print("====================================================\n")


if __name__ == "__main__":
    asyncio.run(main())

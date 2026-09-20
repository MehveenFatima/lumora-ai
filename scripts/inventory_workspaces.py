import asyncio
from backend.app.db.connection import get_db_pool

async def inventory():
    pool = await get_db_pool()
    if not pool:
        print("No pool connection!")
        return
    async with pool.acquire() as conn:
        ws_rows = await conn.fetch('''
            SELECT w.id, w.name, w.created_at, w.overall_mastery,
                   COUNT(d.id) as doc_count,
                   COALESCE(array_agg(d.filename) FILTER (WHERE d.id IS NOT NULL), '{}') as docs
            FROM workspaces w
            LEFT JOIN documents d ON d.workspace_id = w.id
            GROUP BY w.id, w.name, w.created_at, w.overall_mastery
            ORDER BY w.created_at ASC
        ''')
        doc_total = await conn.fetchval("SELECT COUNT(*) FROM documents")
        print(f"Total workspaces in DB: {len(ws_rows)}")
        print(f"Total documents in DB: {doc_total}")
        for r in ws_rows:
            docs_preview = r['docs'][:3]
            print(f"ID: {r['id']} | Name: {r['name']} | Docs: {r['doc_count']} | Files: {docs_preview}")

asyncio.run(inventory())

import asyncio
from backend.app.db.connection import get_db_pool

async def check_fks():
    pool = await get_db_pool()
    if not pool:
        print("No DB connection")
        return
    async with pool.acquire() as conn:
        fks = await conn.fetch('''
            SELECT
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                rc.delete_rule
            FROM 
                information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                JOIN information_schema.referential_constraints AS rc
                  ON rc.constraint_name = tc.constraint_name
            WHERE ccu.table_name = 'workspaces';
        ''')
        for fk in fks:
            print(f"{fk['table_name']}.{fk['column_name']} -> workspaces ({fk['delete_rule']})")

asyncio.run(check_fks())

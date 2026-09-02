# Database Migrations Guide — LumoraAI

## Running the Migration on Supabase PostgreSQL

1. Open your **Supabase Dashboard** -> **SQL Editor**.
2. Copy and paste the contents of `001_initial_schema.sql`.
3. Click **Run**.
4. Verify that:
   - `vector` extension is enabled (`pgvector`).
   - Tables `workspaces`, `documents`, `document_chunks`, `tutor_conversations`, `tutor_messages` are created.
   - HNSW cosine similarity index `idx_document_chunks_embedding_hnsw` is established.

## Environment Connection

Add your Supabase PostgreSQL connection string to your `backend/.env`:
```env
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
```

# Scripts

Developer utilities for seeding, verifying and inspecting a local LumoraAI environment.
Run them from the **repository root**. Most of them call the running API (`:8000` direct or
`:3000` through the Next.js proxy) or connect to the database in `DATABASE_URL`.

## Run the app

| Script | Purpose |
| :--- | :--- |
| `start_dev_all.mjs` | Starts FastAPI (`:8000`) and Next.js (`:3000`) together (`npm run dev:all`). |

## Seed data

| Script | Purpose |
| :--- | :--- |
| `download_seed_pdfs.py` | Downloads the public evaluation corpus (MIT xv6 book, CMU 15-445 notes, Stanford CS229 notes, IETF RFC 9293) into `backend/data/seed_pdfs/`. |
| `reset_and_seed_real_workspaces.py` | **Resets the database** and seeds four workspaces from those PDFs: chunks, a template-generated question bank, curated flashcards, topics and study-plan milestones. It also writes demo starting mastery values (0.75 for the first two topics, 0.35 for the rest), so these are seeded, not earned. Uses deterministic offline embeddings, so no API quota is spent; if you run the app with a Gemini key, re-upload the PDFs through the UI to get Gemini embeddings that match Gemini-embedded queries. |
| `seed_presentation_data.py` | Ingests the 12 PDFs in `lumora_demo_content_pack/` through the real upload pipeline (`npm run seed:presentation`). Requires the API to be running. |
| `seed_dsa_presentation_data.py` | Generates and ingests a small Data Structures & Algorithms workspace (`dsa`). |
| `cleanup_dsa_seed.py` | Removes the documents seeded by `seed_dsa_presentation_data.py`. |
| `cleanup_test_workspaces.py` | Deletes workspaces left behind by tests, preserving the seeded ones. |

## Verify a running environment

| Script | Purpose |
| :--- | :--- |
| `verify_presentation_readiness.py` | End-to-end checks across the four seeded workspaces. |
| `verify_workspace_creation_and_rag.py` | Creates a workspace, uploads a document and asks the tutor through the proxy. |
| `verify_dsa_presentation_seed.py` | Checks the `dsa` workspace seed. |
| `test_proxy_quiz_latency.py` | Times quiz session creation, question fetch and answer submission through the proxy. |
| `test_client_proxy_contracts.mjs` | Checks the browser API client and proxy contracts. |
| `e2e-rag-acceptance-test.ts`, `test-real-pdf-rag.ts`, `test-ssl-document-resolution.ts` | TypeScript acceptance checks; run with `npx tsx scripts/<file>.ts`. |

## Inspect the database

| Script | Purpose |
| :--- | :--- |
| `diagnose_phase0.py` | Health diagnostics for the API, proxy and database. |
| `inventory_workspaces.py` | Lists workspaces and their documents. |
| `check_fks.py` | Lists foreign keys that reference `workspaces` and their delete rules. |

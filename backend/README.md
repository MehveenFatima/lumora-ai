# LumoraAI backend

FastAPI service behind LumoraAI. It handles document ingestion, retrieval-augmented tutoring, adaptive quizzes, Bayesian Knowledge Tracing and the learner profile. Everything is served under `/api/v1` and scoped to a workspace.

See the [main README](../README.md) for the full project overview and [`docs/architecture.md`](../docs/architecture.md) for how retrieval, BKT and the adaptive quiz work.

## Run

Imports use the `backend.app` package, so run commands from the **repository root**:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp .env.example .env                                  # then fill in your keys
python -m uvicorn backend.app.main:app --reload --port 8000
```

- Interactive API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/v1/health>

Without `DATABASE_URL` the API uses an in-memory store. Without `GEMINI_API_KEY` / `OPENROUTER_API_KEY` it falls back to deterministic offline embeddings and extractive, source-only answers. That keeps local development and the test suite independent of external services.

## Layout

```
backend/app/
├── main.py              FastAPI app, CORS, startup checks
├── api/routes/          HTTP endpoints (workspaces, documents, tutor, quizzes, mastery, …)
├── services/            Parsing, chunking, embeddings, retrieval, tutor, quiz, BKT, question quality
├── repositories/        PostgreSQL (asyncpg + pgvector) access with an in-memory fallback
├── ai/                  Gemini + OpenAI-compatible providers behind a failover gateway
├── schemas/             Pydantic request/response models
├── core/                Settings and logging
└── db/migrations/       SQL migrations (apply in order)
```

## Endpoints

| Area | Method & path |
| :--- | :--- |
| Health | `GET /health` |
| Workspaces | `POST /workspaces` · `GET /workspaces` · `GET /workspaces/{id}` · `DELETE /workspaces/{id}` |
| Documents | `POST /workspaces/{id}/documents` · `GET /workspaces/{id}/documents` · `GET /documents/{doc_id}` · `GET /documents/{doc_id}/view` · `GET /documents/{doc_id}/download` · `DELETE /documents/{doc_id}` |
| Tutor | `POST /workspaces/{id}/tutor` · `GET /workspaces/{id}/tutor/history` |
| Quizzes | `POST /workspaces/{id}/quizzes` · `GET …/quizzes/active` · `GET …/quizzes/history` · `GET …/quizzes/{quiz_id}` · `GET …/questions/{question_id}` · `POST …/questions/{question_id}/attempt` · `POST …/quizzes/{quiz_id}/next-batch` · `POST …/quizzes/{quiz_id}/complete` |
| Mastery | `GET /workspaces/{id}/learner-profile` · `GET …/mastery` · `GET …/mastery/topics` · `GET …/mastery/topics/{topic}` · `POST …/mastery/seed` (development and tests only, disabled when `ENVIRONMENT=production`) |
| Study tools | `GET`/`POST …/flashcards[/generate]` · `GET`/`POST …/study-plan[/generate]` · `POST …/study-plan/tasks/{task_id}/toggle` |
| Activity | `GET`/`POST /workspaces/{id}/activity` · `GET /activities` |

All paths are relative to `/api/v1`.

## Tests

```bash
python -m pytest backend/tests -q
```

The suite (108 tests) runs against the in-memory store and needs no external services. If a `.env` with real API keys is present, some tests will call the AI providers, so leave the keys unset for a fully offline run. To run against PostgreSQL instead, point `DATABASE_URL` at a **disposable** database with the migrations applied. The tests create and delete workspaces, so never point them at a database you care about.

# LumoraAI Backend — Workspace-Scoped RAG AI Tutor

FastAPI backend providing document ingestion, page-aware chunking, Google Gemini embeddings, workspace-isolated vector search via Supabase pgvector, and grounded AI tutoring.

---

## 1. Quick Start

### Prerequisites
- Python 3.10+
- (Optional) Supabase PostgreSQL database with `pgvector` enabled
- Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/)

### Setup Environment
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### Run Server
```bash
uvicorn app.main:app --reload --port 8000
```
- Interactive API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/v1/health`

---

## 2. API Endpoints

| Method | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Health check endpoint |
| `POST` | `/api/v1/workspaces/{workspace_id}/documents` | Upload & index PDF, DOCX, PPTX, TXT into workspace |
| `GET` | `/api/v1/workspaces/{workspace_id}/documents` | List all indexed documents for a workspace |
| `GET` | `/api/v1/documents/{document_id}` | Inspect document status & chunk metadata |
| `DELETE` | `/api/v1/documents/{document_id}` | Delete document and vector chunks |
| `POST` | `/api/v1/workspaces/{workspace_id}/tutor` | Ask grounded question strictly based on workspace notes |
| `GET` | `/api/v1/workspaces/{workspace_id}/tutor/history` | Retrieve conversation history |

---

## 3. Running Test Suites
```bash
pytest backend/tests -v
```
To run the RAG evaluation suite:
```bash
pytest backend/tests/test_rag_evaluation.py -v
```

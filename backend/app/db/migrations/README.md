# Database migrations

Plain SQL migrations for PostgreSQL 15+ with the `pgvector` extension (Supabase or self-hosted).
Apply them **in order**; each file is idempotent (`CREATE ... IF NOT EXISTS`).

| File | Adds |
| :--- | :--- |
| `001_initial_schema.sql` | `vector` + `uuid-ossp` extensions, `workspaces`, `documents`, `document_chunks` (768-d embeddings, HNSW cosine index), `tutor_conversations`, `tutor_messages` |
| `002_adaptive_quiz_schema.sql` | `quiz_sessions`, `quiz_questions`, `quiz_attempts` |
| `003_adaptive_learning_bkt_schema.sql` | `learner_concept_mastery`, `learner_knowledge_gaps`, `quiz_question_fingerprints`; adaptation columns on `quiz_sessions` |
| `004_topic_mastery_and_learner_profile_schema.sql` | `learner_topic_mastery`, `learner_mastery_snapshots`; trend and confidence columns on `learner_concept_mastery` |
| `005_question_quality_and_anti_leakage_schema.sql` | `quality_score` and `question_type` on `quiz_questions` |
| `006_secondary_presentation_features.sql` | `flashcards`, `study_plans`, `activity_events` |
| `007_workspace_question_bank.sql` | `workspace_question_bank` (validated questions served by the adaptive quiz) |

## Supabase

1. Open **SQL Editor** in the Supabase dashboard.
2. Run each file above in order.
3. Put the connection string in `.env`:

```env
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
```

## Local PostgreSQL

```bash
# requires PostgreSQL with the pgvector extension installed
createdb lumora
for f in backend/app/db/migrations/0*.sql; do psql -d lumora -v ON_ERROR_STOP=1 -f "$f"; done
```

# LumoraAI API (FastAPI). Build from the repository root:
#   docker build -f backend/Dockerfile -t lumora-api .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --upgrade pip && pip install -r backend/requirements.txt

COPY backend/app backend/app
# Seed script and the public course PDFs it indexes (for demo data)
COPY scripts scripts
COPY backend/data/seed_pdfs backend/data/seed_pdfs

RUN useradd --create-home --uid 10001 lumora \
    && mkdir -p backend/data/documents \
    && chown -R lumora:lumora /app
USER lumora

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/v1/health', timeout=4)"

# Apply pending migrations (when a database is configured), then serve
CMD ["sh", "-c", "if [ -n \"$DATABASE_URL\" ]; then python -m backend.app.cli migrate; fi && exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]

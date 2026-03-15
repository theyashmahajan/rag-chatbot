# Local-First RAG Chatbot

Production-oriented open-source RAG chatbot scaffold with:
- Next.js web app
- FastAPI backend
- Celery worker
- PostgreSQL + Redis + Qdrant + Ollama + MinIO via Docker Compose

## Quick Start

1. Copy env file:
```bash
cp .env.example .env
```

2. Start infra + apps:
```bash
docker compose -f infra/docker/docker-compose.yml up --build
```
or:
```bash
make up
```

3. Open:
- Web: http://localhost:3000
- API docs: http://localhost:8000/docs

4. Pull local models in Ollama (first-time):
```bash
docker compose -f infra/docker/docker-compose.yml exec ollama ollama pull qwen2.5:7b-instruct
docker compose -f infra/docker/docker-compose.yml exec ollama ollama pull nomic-embed-text
```

5. (Optional, recommended) run Alembic migrations:
```bash
docker compose -f infra/docker/docker-compose.yml exec api alembic -c /app/apps/api/alembic.ini upgrade head
```

## Current Scope

Implemented now:
- Auth (`/auth/signup`, `/auth/login`, `/auth/me`)
- Token refresh (`/auth/refresh`)
- Chats (`/chats`)
- Upload endpoint with per-chat file limit (`/chats/{chat_id}/documents`)
- Async ingestion worker with extraction + chunking for PDF, DOCX, TXT/MD, PNG, JPG
- Qdrant vector indexing per chunk during ingestion
- Message endpoint with vector retrieval + Ollama generation (`/chats/{chat_id}/messages`)
- Streaming endpoint (`/chats/{chat_id}/messages/stream`) with SSE
- Basic API rate limiting for auth and message endpoints

Next:
- Alembic migrations and schema versioning
- Refresh-token rotation with revocation store
- Redis-backed distributed rate limiting

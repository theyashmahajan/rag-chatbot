# Local-First Open-Source RAG Chatbot - Implementation Plan

## 1) Product Goal
Build a production-ready, local-first RAG chatbot where users can:
- Sign up/login and manage their own chats.
- Upload up to 4 files per chat/session.
- Ask questions, request summaries, and request modifications based on uploaded documents.
- Work with multiple document formats: PDF, DOCX, TXT/MD, images (PNG/JPG), and optionally CSV/XLSX.
- Keep all data on local infrastructure by default.

Non-goal for v1: cloud-managed proprietary APIs.

## 2) Core Principles
- Local-first storage: files, embeddings, metadata, and chat history stay on your machine/server.
- Open-source only: model and infrastructure choices must be free to self-host.
- Production baseline: auth, RBAC-lite, audit events, rate limits, logging, retries, backups.
- Reproducible setup: one-command start via Docker Compose for new contributors.

## 3) Recommended Architecture

### Frontend
- Next.js (App Router) + TypeScript + Tailwind + shadcn/ui.
- Features: login/signup, workspace/chats, upload UI, citations, streaming responses.

### Backend API
- FastAPI (Python 3.11+).
- Responsibilities:
  - Auth/session verification.
  - File upload and validation.
  - Parsing + chunking pipeline trigger.
  - Retrieval + generation orchestration.
  - Chat/history APIs.

### Worker / Background Processing
- Celery workers + Redis broker (or RQ for simpler setup).
- Jobs:
  - OCR/parsing.
  - Embedding generation.
  - Vector indexing.
  - Document reprocessing/versioning.

### Datastores
- PostgreSQL: users, sessions, chats, messages, document metadata, processing states, audit logs.
- Qdrant (local container): vector embeddings for retrieval.
- Local object storage:
  - Option A: MinIO (S3-compatible, self-hosted).
  - Option B (simpler): local filesystem in `storage/` with strict path isolation.

### Model Layer (Open-source)
- LLM inference: Ollama (local).
  - Start with `qwen2.5:7b-instruct` (balanced quality/speed).
  - Optional better quality if GPU allows: `llama3.1:8b-instruct`.
- Embeddings:
  - `BAAI/bge-m3` (strong multilingual retrieval), or
  - `nomic-embed-text` via Ollama for easier deployment.
- OCR:
  - Tesseract OCR (+ `pytesseract`) for images/scanned PDFs.

### Retrieval Strategy
- Hybrid retrieval:
  - Dense vector search in Qdrant.
  - Optional BM25 fallback via PostgreSQL full-text or Whoosh.
- Re-ranking (optional phase 2): cross-encoder reranker for higher precision.
- Citation-first prompting: include source snippets with doc name/page/chunk id.

## 4) Data Model (Minimum)
- `users` (id, email, password_hash, created_at).
- `sessions` (id, user_id, expires_at).
- `chats` (id, user_id, title, created_at, updated_at).
- `messages` (id, chat_id, role, content, tokens, created_at).
- `documents` (id, user_id, chat_id, file_name, mime_type, size, status, version, created_at).
- `document_chunks` (id, document_id, chunk_index, text, metadata_json).
- `ingestion_jobs` (id, document_id, state, error, started_at, finished_at).
- `audit_events` (id, user_id, event_type, payload_json, created_at).

## 5) Upload and Processing Flow
1. User uploads 1-4 documents to a chat.
2. API validates type/size/count and stores raw file locally.
3. Worker parses by MIME type:
   - PDF: PyMuPDF / pdfplumber; OCR fallback when scanned.
   - DOCX: python-docx.
   - TXT/MD: direct read.
   - Images: OCR pipeline.
4. Normalize extracted text and split into chunks (semantic + size cap).
5. Generate embeddings per chunk.
6. Upsert vectors to Qdrant with payload (user_id/chat_id/doc_id/page/chunk).
7. Mark document status as `indexed`.

## 6) Query Flow
1. User asks a question in a chat.
2. API embeds query and retrieves top-k chunks filtered by `user_id` + `chat_id`.
3. Build prompt with:
   - system instruction,
   - recent conversation history,
   - top chunks with citations.
4. LLM generates answer (streaming).
5. Store user + assistant messages in `messages`.
6. Return answer with citations and confidence/coverage flags.

## 7) Authentication and Security
- Auth for v1: email/password with hashed passwords (Argon2).
- JWT access + refresh tokens (HTTP-only cookie).
- Enforce per-user data isolation in every query filter.
- Limits:
  - max files/chat: 4,
  - max file size: configurable (for example 25MB),
  - rate limits per user/IP.
- Security checks:
  - MIME validation + extension whitelist,
  - malware scan hook (optional local ClamAV),
  - secure file path handling.

## 8) Conversation Memory and History
- Persist all chat turns in PostgreSQL.
- Build context window from:
  - last N turns,
  - optional running summary for long chats.
- Add "regenerate" and "edit message" as phase 2 features.

## 9) Suggested Repository Structure
```
research-paper-analysis/
  apps/
    web/                # Next.js frontend
    api/                # FastAPI backend
    worker/             # Celery worker
  packages/
    shared-types/
    prompt-templates/
  infra/
    docker/
      docker-compose.yml
    scripts/
  docs/
    implementation-plan.md
  storage/              # local files (gitignored)
```

## 10) Install/Setup Requirements

### System Dependencies
- Docker + Docker Compose.
- Python 3.11+.
- Node.js 20+ and pnpm.
- Tesseract OCR.
- Git.

### Services to Run Locally
- PostgreSQL.
- Redis.
- Qdrant.
- MinIO (optional, recommended).
- Ollama.

### Python Packages (API/Worker)
- fastapi, uvicorn, pydantic, sqlalchemy, alembic.
- psycopg[binary], redis, celery.
- qdrant-client, sentence-transformers (if not using Ollama embeddings).
- pypdf/pdfplumber, pymupdf, python-docx, pillow, pytesseract.
- python-multipart, passlib/argon2-cffi, pyjwt.

### Frontend Packages
- next, react, typescript.
- tailwindcss, shadcn/ui.
- react-query, zod, axios.

## 11) Milestone Plan

### Milestone 0 - Foundation (2-3 days)
- Monorepo scaffolding.
- Docker Compose with Postgres/Redis/Qdrant/Ollama/MinIO.
- Basic auth (signup/login/logout).
- Health checks + env config.

### Milestone 1 - Ingestion MVP (4-6 days)
- Upload API with 4-doc/chat limit.
- Parser pipeline for PDF/DOCX/TXT/images.
- Chunking + embeddings + Qdrant upsert.
- Document status tracking UI.

### Milestone 2 - Chat RAG MVP (4-6 days)
- Retrieval and generation API.
- Streaming response UI.
- Citation rendering.
- Persistent chat history.

### Milestone 3 - Hardening (4-7 days)
- Observability: structured logs + metrics.
- Retry logic + dead-letter strategy for failed ingestion.
- Rate limits and file validation hardening.
- Backup/restore scripts for Postgres + storage + Qdrant.

### Milestone 4 - Production Readiness (5-8 days)
- E2E tests for auth/upload/chat.
- Role model (admin/user).
- Deployment docs for single-server self-host.
- Performance tuning for chunking/retrieval latency.

## 12) Definition of Done (v1)
- Users can register/login and create chats.
- Users can upload up to 4 mixed-format files per chat.
- Files are parsed and indexed locally.
- Users can ask document-grounded questions and get cited answers.
- Full conversation history persists per chat.
- System runs fully with open-source components and no paid API dependency.

## 13) Cost and License Notes
- All recommended core components are open source and free to self-host.
- Verify model licenses before distribution in commercial contexts.
- Hardware cost is the primary runtime cost (CPU/GPU/RAM/storage), not software licensing.

## 14) Risks and Mitigations
- OCR quality on low-quality scans: add preprocessing and allow manual correction.
- Hallucinations: enforce citation-only answer mode and confidence flags.
- Large-file latency: async ingestion + progress UI + caching.
- Local machine resource limits: provide model-size profiles (small/medium/large).

## 15) Immediate Next Build Tasks
1. Scaffold monorepo directories and Docker Compose.
2. Implement auth and DB schema migrations.
3. Build ingestion worker and file parser abstraction.
4. Add vector indexing and retrieval API.
5. Build chat UI with streaming + citations.

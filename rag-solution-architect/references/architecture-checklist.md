# Architecture Checklist

## 1. Product Scope
- Confirm user personas and expected usage volume.
- Define per-chat document upload limits and size caps.
- Define required document formats and OCR expectations.

## 2. Local-First Constraints
- Confirm data never leaves local environment by default.
- Choose file storage strategy (filesystem vs self-hosted object store).
- Define backup and restore procedures for files and databases.

## 3. Model and Retrieval
- Choose local LLM runtime (Ollama/vLLM).
- Choose embedding model and dimension compatibility.
- Decide chunking strategy and metadata schema.
- Enforce retrieval filters by user and chat scope.
- Require answer citations to source chunks.

## 4. Platform Components
- Frontend framework and streaming strategy.
- Backend API framework and auth/session pattern.
- Worker queue and retry strategy.
- Databases: relational + vector + cache.

## 5. Security Baseline
- Password hashing and token strategy.
- File validation and content-type enforcement.
- Per-user authorization checks on every API path.
- Rate limits for auth and chat endpoints.
- Audit events for upload, delete, and admin actions.

## 6. Reliability and Operations
- Health/readiness checks for all services.
- Structured logs with correlation IDs.
- Metrics for ingestion, retrieval latency, and model latency.
- Dead-letter handling for failed ingestion jobs.

## 7. Delivery Plan
- Milestones with acceptance criteria.
- Test strategy: unit, integration, e2e.
- Environment setup documentation for new contributors.
- Definition of done for MVP and hardening phases.

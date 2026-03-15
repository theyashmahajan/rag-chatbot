---
name: rag-solution-architect
description: Design and review production-grade, local-first, open-source RAG chatbot architectures. Use when planning system architecture, storage strategy, model stack, ingestion/retrieval flow, scalability, security, deployment, and phased implementation plans for multi-document conversational AI products.
---

# RAG Solution Architect

## Overview
Use this skill to produce implementation-ready architecture and rollout plans for local/self-hosted RAG chat systems with authentication, chat memory, document ingestion, and retrieval-grounded generation.

## Workflow
1. Clarify product and deployment constraints.
2. Select an open-source stack aligned to hardware and latency targets.
3. Design ingestion, indexing, retrieval, and generation pipelines.
4. Define data model, security controls, and observability requirements.
5. Produce phased milestones with deliverables and acceptance criteria.

## Architecture Checklist
Use [references/architecture-checklist.md](references/architecture-checklist.md) as the primary checklist before finalizing any plan.

## Output Contract
Every final architecture plan should include:
- System components and responsibilities.
- Data flow for upload, indexing, and query answering.
- Tech stack with free/open-source alternatives.
- Install/setup prerequisites.
- Schema outline for users/chats/documents/messages.
- Security baseline (auth, isolation, limits, validation).
- Milestone-based implementation roadmap.
- Risks and mitigation notes.

## Constraints
- Prefer local-first defaults with optional cloud extensions.
- Avoid paid/proprietary model dependencies unless explicitly requested.
- Enforce per-user data isolation at the retrieval filter level.
- Require citation-grounded response behavior for document QA.
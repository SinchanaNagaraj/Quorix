# Quorix System Architecture

Quorix is an **Intelligent Context Selection and Retrieval Optimization Engine** designed to sit between user queries and multi-source knowledge retrieval infrastructure.

## System Overview

```
                      User Query
                          │
                          ▼
             ┌─────────────────────────┐
             │ Phase 3: Query Analysis │
             │ & Source Selection      │
             └────────────┬────────────┘
                          │ (Selected Source Profiles)
                          ▼
             ┌─────────────────────────┐
             │ Phase 4: Budget Manager │
             └────────────┬────────────┘
                          │ (Allocated Token/Retrieval Budget)
                          ▼
             ┌─────────────────────────┐
             │ Phase 2: Ingestion &    │
             │ Vector/Relational Store │
             │ (Qdrant & PostgreSQL)   │
             └────────────┬────────────┘
                          │ (Retrieved Chunks & Metadata)
                          ▼
             ┌─────────────────────────┐
             │ Phase 5: Synthesis &    │
             │ Evidence Verification   │
             └─────────────────────────┘
```

## Architectural Phases

- **Phase 1: Foundation & Infrastructure**: Database connections (PostgreSQL/Supabase, Qdrant client), FastAPI entry points, configuration management, and environment setup.
- **Phase 2: Ingestion Pipeline & Normalization**: Standardized ingestion adapters for Documents (`.md`, `.pdf`, `.txt`), Engineering Conversations (`.json`), and Development Tickets (`.json`). Chunking service, SentenceTransformers embedding, and vector upsert into Qdrant with PostgreSQL metadata storage.
- **Phase 3: Query Analysis & Intelligent Source Selection**: Decides **WHERE** to retrieve before deciding **WHAT** to retrieve. Evaluates candidate sources across Query Relevance (35%), Authority (25%), Freshness (20%), and Expected Directness (20%).
- **Phase 4: Retrieval Budget Manager** *(Upcoming)*: Dynamic allocation of token, chunk, and network budgets across the prioritized sources.
- **Phase 5: Evidence & Contradiction Engine** *(Upcoming)*: Verification, conflict detection, and answer synthesis.

For complete specifications and scoring details for Phase 3, see [PHASE3_ARCHITECTURE.md](file:///G:/OneDrive/Desktop/Hackathon/docs/PHASE3_ARCHITECTURE.md).

# Quorix

**Intelligent Context Selection & Pre-Retrieval Optimization Engine**

Quorix is an intelligent RAG context optimization system designed to eliminate redundant vector retrieval operations, stale/conflicting context, latency, and LLM inference costs.

Its central operating principle is:
> **Decide WHERE to look before deciding WHAT to retrieve.**

```
                      User Natural-Language Query
                                   │
                                   ▼
                      ┌──────────────────────────┐
                      │  Query Analysis Engine   │
                      │  - Structured Intents    │
                      │  - Entities & Keywords   │
                      │  - Temporal Requirements │
                      │  - Info Categories       │
                      └────────────┬─────────────┘
                                   │
                                   │ QueryAnalysis
                                   ▼
                      ┌──────────────────────────┐
                      │ Source Selection Engine  │
                      │  - Source Profiles       │
                      │  - 4-Factor Scoring      │
                      │  - Deterministic Ranking │
                      │  - Policy & Thresholding │
                      └────────────┬─────────────┘
                                   │
                                   │ SourceSelectionResult
                                   ▼
                       Phase 4: Retrieval Budget
                      (Targeted Retrieval Only)
```

---

## Architectural Roadmap

- **Phase 1: Foundation & Infrastructure**: Database connections (PostgreSQL/Supabase, Qdrant client), FastAPI entry points, configuration management, and environment setup.
- **Phase 2: Ingestion Pipeline & Normalization**: Standardized ingestion adapters for Documents (`.md`, `.pdf`, `.txt`), Engineering Conversations (`.json`), and Development Tickets (`.json`). Structural chunking, SentenceTransformers embedding, and vector upsert into Qdrant with PostgreSQL metadata storage.
- **Phase 3: Query Analysis & Intelligent Source Selection**: Pre-retrieval routing layer. Analyzes query characteristics and scores candidate sources across Query Relevance (35%), Authority (25%), Freshness (20%), and Expected Directness (20%).
- **Phase 4: Retrieval Budget Manager** *(Upcoming)*: Dynamic allocation of token, chunk, and network budgets across prioritized sources.
- **Phase 5: Evidence & Contradiction Engine** *(Upcoming)*: Verification, conflict detection, and answer synthesis.

---

## 4-Factor Source Scoring Formula

Every registered knowledge source profile is evaluated across 4 standardized dimensions:

$$S(q, s) = (0.35 \times R) + (0.25 \times A) + (0.20 \times F) + (0.20 \times D)$$

1. **Query Relevance ($R = 0.35$)**: Semantic and concept matching, category overlap, query intent affinity, and entity coverage.
2. **Source Authority ($A = 0.25$)**: Trustworthiness of the source origin (approved architecture, official documentation, tickets, discussions).
3. **Query-Aware Freshness ($F = 0.20$)**:
   - `CURRENT`: Exponential decay $F = e^{-\ln(2) \cdot \Delta / \tau}$ relative to reference date with configurable half-life ($\tau = 180$ days).
   - `HISTORICAL`: Event alignment and decision milestone recognition without penalizing age.
   - `COMPARATIVE`: Dual-temporal coverage (preserves both baseline documentation and transition rationale).
   - `TIME_INDEPENDENT`: Neutral temporal score ($0.75$).
4. **Expected Directness ($D = 0.20$)**: Evaluates likelihood that the source directly answers the specific intent (e.g. configuration $\rightarrow$ documentation; bugs $\rightarrow$ tickets; rationale $\rightarrow$ discussions).

---

## Getting Started

### 1. Installation

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Running Tests

```bash
cd backend
pytest -v
```

All 88 unit, integration, and architecture boundary tests pass cleanly:
- Guaranteed zero Qdrant calls, zero chunk loading, and zero LLM answer generation during query analysis and source selection.
- Tested across canonical scenarios and manual routing evaluations.

---

## Documentation

- [PHASE3_ARCHITECTURE.md](docs/PHASE3_ARCHITECTURE.md): Complete Phase 3 technical specification and scoring formulas.
- [PHASE3_VALIDATION_REPORT.md](docs/PHASE3_VALIDATION_REPORT.md): Manual routing evaluation report on Project Atlas dataset.
- [API.md](docs/API.md): REST API endpoints and payload schemas.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md): System architecture and data flow.

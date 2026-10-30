# Quorix Phase 3: Query Analysis & Intelligent Source Selection Engine

## Overview

Quorix is an **Intelligent Context Selection and Retrieval Optimization Engine**. Traditional RAG architectures retrieve chunks from every available knowledge source before evaluating relevance, resulting in redundant network calls, bloated context windows, inflated LLM costs, and conflicting or stale evidence.

**Phase 3** introduces the core innovation of Quorix:
> **Deciding WHERE to look BEFORE deciding WHAT to retrieve.**

```
                     User Natural-Language Query
                                  │
                                  ▼
                     ┌──────────────────────────┐
                     │  Query Analysis Engine   │
                     │  - Structured Intents    │
                     │  - Entities & Keywords   │
                     │  - Temporal Requirement │
                     │  - Info Categories       │
                     └────────────┬─────────────┘
                                  │
                                  │ QueryAnalysis Model
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
                     (Selective Retrieval Only)
```

---

## 1. Query Analysis Engine Architecture

The Query Analysis Engine transforms natural language queries into a strongly-typed, validated Pydantic model (`QueryAnalysis`).

### 1.1 Architecture & Components
- **`QueryAnalyzer` (`app.intelligence.query_analysis.analyzer`)**: Primary orchestrator. If Google GenAI (`gemini_api_key`) is configured, invokes Gemini with structured JSON output and schema validation.
- **`Fallback Engine` (`app.intelligence.query_analysis.fallback`)**: Fully deterministic, rule-based analysis ensuring zero downtime if external APIs or network connectivity fail.
- **`Schemas` (`app.intelligence.query_analysis.schemas`)**: Enums and Pydantic models for validated intent classifications, temporal requirements, information categories, and potential source types.

### 1.2 QueryAnalysis Data Structure
```python
class QueryAnalysis(BaseModel):
    original_query: str
    normalized_query: str
    primary_intent: QueryIntent
    secondary_intents: list[QueryIntent]
    entities: list[str]
    technical_keywords: list[str]
    information_requirements: list[str]
    temporal_requirement: TemporalRequirement
    expected_information_categories: list[InformationCategory]
    potential_source_types: list[SourceType]
    requires_multiple_sources: bool
    analysis_explanation: str
```

### 1.3 Classification Enums
- **`QueryIntent`**: `FACTUAL_LOOKUP`, `TECHNICAL_EXPLANATION`, `HISTORICAL_REASONING`, `CONFIGURATION_LOOKUP`, `TROUBLESHOOTING`, `IMPLEMENTATION_DETAILS`, `COMPARISON`, `CHANGE_ANALYSIS`, `DECISION_HISTORY`, `MULTI_PART_QUERY`, `GENERAL_INFORMATION`.
- **`TemporalRequirement`**:
  - `CURRENT`: Active configurations, current settings, latest values.
  - `HISTORICAL`: Original design motivations, past decisions, deprecated features.
  - `COMPARATIVE`: Changes across time, version upgrades, old vs. new.
  - `TIME_INDEPENDENT`: Architectural concepts, invariants, general domain knowledge.
  - `MIXED`: Multi-part queries spanning both past rationale and current state.

---

## 2. Source Metadata Abstraction

To ensure decoupling from underlying storage engines (PostgreSQL, Qdrant, future GitHub/Slack/Jira adapters), sources expose a common abstraction: `SourceProfile`.

```python
class SourceProfile(BaseModel):
    source_id: str
    source_type: SourceType  # DOCUMENT, CONVERSATION, TICKET
    source_name: str
    source_description: str
    authority_level: str
    authority_score: float  # [0.0, 1.0]
    last_updated_at: datetime | None
    available_content_categories: list[str]
    supported_query_categories: list[str]
    retrieval_cost: float | None
    source_status: str
```

The `SourceRegistry` (`app.intelligence.source_selection.registry`) populates these profiles from `data/source_registry.json` or database tables, **without retrieving raw text or vector embeddings for document chunks**.

---

## 3. Source Scoring Formula

Every candidate source is evaluated across four normalized factors $[0.0, 1.0]$:

$$S(q, s) = (w_R \times R) + (w_A \times A) + (w_F \times F) + (w_D \times D)$$

Where:
- $R$ = **Query Relevance** ($w_R = 0.35$)
- $A$ = **Source Authority** ($w_A = 0.25$)
- $F$ = **Source Freshness** ($w_F = 0.20$)
- $D$ = **Expected Directness** ($w_D = 0.20$)

Weights are validated at startup: non-negative and $\sum w_i = 1.0$.

> [!NOTE]
> Scoring weights ($0.35, 0.25, 0.20, 0.20$) and authority mapping values are configurable initial heuristics based on the PRD specification, not experimentally proven universal optima.

---

## 4. Explanation of the Four Scoring Factors

### 4.1 Query Relevance ($R$, 35%)
Evaluates semantic and categorical alignment between the query characteristics and the source profile:
- **Semantic Profile Similarity**: Cosine similarity between query embedding and source profile embedding using `EmbeddingService` (or token overlap fallback).
- **Category Overlap**: Intersection between query `expected_information_categories` and source `available_content_categories`.
- **Intent Alignment**: Natural affinity of source type to primary/secondary query intent.
- **Entity Matching**: Coverage of named entities within source descriptions.

### 4.2 Source Authority ($A$, 25%)
Measures the trustworthiness of the source origin using deterministic heuristics:
- `APPROVED_ARCHITECTURE`: $1.00$
- `OFFICIAL_TECHNICAL_DOCUMENTATION`: $0.95$
- `VERIFIED_ENGINEERING_DECISION`: $0.90$
- `MAINTAINED_CONFIGURATION_RECORD`: $0.90$
- `RESOLVED_DEVELOPMENT_TICKET`: $0.85$
- `ACTIVE_DEVELOPMENT_TICKET`: $0.75$
- `ENGINEERING_CONVERSATION`: $0.70$
- `INFORMAL_DISCUSSION`: $0.55$
- `UNKNOWN_AUTHORITY`: $0.40$

### 4.3 Source Freshness ($F$, 20%)
Freshness is strictly **query-dependent** and operates on an **injectable reference clock/date**:
- **Production Reference Clock**: Defaults to `datetime.now(timezone.utc)` in production. An explicit reference date (e.g. `2025-03-31T00:00:00Z` for the Project Atlas dataset) can be injected for reproducible testing and benchmark evaluation.
- **`CURRENT` queries**: Pure mathematical exponential decay $F = e^{-\ln(2) \cdot \Delta / \tau}$ where $\Delta$ is age in days and $\tau = 180$ days (half-life). A source updated today scores $1.0$, a source updated $180$ days ago scores $0.50$, and a source updated $360$ days ago scores $0.25$.
- **`HISTORICAL` queries**: Evaluates temporal relevance to the specific historical event or milestone. Sources documenting decision rationale or aligning with query-extracted temporal anchors (e.g. dates, years, incident post-mortems) score $0.85–0.95$ without artificial age penalization. Sources lacking historical metadata score neutrally ($0.70$).
- **`COMPARATIVE` queries**: High scores for sources documenting historical decisions and current baselines ($0.88–0.92$), coupled with selection policy preservation.
- **`TIME_INDEPENDENT` queries**: Neutral temporal score ($0.75$) eliminating recency bias for foundational architecture and concepts.
- **`MIXED` queries**: Blends current exponential decay with historical milestone coverage.
- **Missing timestamps**: Handled safely with configurable conservative score ($0.50$).
- **Future timestamps**: Handled safely without clock skew crashes ($1.00$).

### 4.4 Expected Directness ($D$, 20%)
Estimates likelihood that the source directly answers the core question:
- Configuration queries $\rightarrow$ Technical Documents ($0.95$), Tickets ($0.75$), Conversations ($0.40$).
- Historical decision queries $\rightarrow$ Conversations ($0.95$), Tickets ($0.80$), Documents ($0.55$).
- Troubleshooting/Bug queries $\rightarrow$ Tickets ($0.95$), Conversations ($0.85$), Documents ($0.50$).

---

## 5. Worked Scoring Example

Consider:
- **Query**: *"Why was Redis caching introduced?"*
- **Candidate Source**: *Atlas Engineering Conversations (`SRC-CONV`)*

**Factor Breakdown**:
1. **Relevance ($R$)**: $0.95$ (High semantic and category overlap for decision rationale and caching)
2. **Authority ($A$)**: $0.85$ (Verified engineering discussions)
3. **Freshness ($F$)**: $0.90$ (Historical intent; older discussions are temporally relevant)
4. **Directness ($D$)**: $0.95$ (Engineering discussions directly capture rationale)

**Weighted Score Calculation**:
$$S = (0.35 \times 0.95) + (0.25 \times 0.85) + (0.20 \times 0.90) + (0.20 \times 0.95)$$
$$S = 0.3325 + 0.2125 + 0.1800 + 0.1900 = 0.9150$$

**Decision**: `SELECTED` (Score $0.915 \ge 0.55$ threshold).

---

## 6. Source Selection Policy & Budget Semantics

1. **Ranking**: Sources are ranked in descending order by `weighted_score`. Ties are broken deterministically by `authority_score`, then `source_id`.
2. **Threshold Filtering**: Candidate sources must satisfy $S(q, s) \ge \text{selection\_threshold}$ ($0.55$).
3. **Capacity Budget**: At most `max_selected_sources` ($3$) source profiles are selected. Multiple source profiles of the same type (e.g. multiple distinct document or ticket profiles) can be selected if they best serve the query.
4. **Multi-Part & Temporal Preservation**: When queries require comparative or mixed evidence, both historical rationale candidates and current baseline specifications are preserved in the selected set.
5. **Incomplete Coverage Reporting**: If all information requirements cannot be satisfied within the configured selection budget or available sources, unmet requirements are explicitly reported in `unmet_information_requirements` and surfaced in the selection summary. The system never silently drops requirements.
6. **No Suitable Source**: If no source meets the threshold, returns an explicit `NO_SUITABLE_SOURCE` status.


---

## 7. API Endpoints

### 7.1 POST `/api/v1/query/analyze`
**Request**:
```json
{
  "query": "Why was Redis caching introduced, and what is its current TTL configuration?"
}
```

**Response**:
```json
{
  "query_analysis": {
    "original_query": "Why was Redis caching introduced, and what is its current TTL configuration?",
    "normalized_query": "Why was Redis caching introduced, and what is its current TTL configuration?",
    "primary_intent": "HISTORICAL_REASONING",
    "secondary_intents": ["CONFIGURATION_LOOKUP"],
    "entities": ["Redis", "TTL", "caching"],
    "technical_keywords": ["Redis", "caching", "introduced", "current", "TTL", "configuration"],
    "information_requirements": [
      "Information on historical reasoning for Redis, TTL, caching",
      "Information on current configuration for Redis, TTL, caching"
    ],
    "temporal_requirement": "MIXED",
    "expected_information_categories": [
      "HISTORICAL_REASONING",
      "CURRENT_CONFIGURATION"
    ],
    "potential_source_types": ["conversation", "document", "ticket"],
    "requires_multiple_sources": true,
    "analysis_explanation": "Query evaluated as HISTORICAL_REASONING with temporal requirement MIXED..."
  }
}
```

### 7.2 POST `/api/v1/query/select-sources`
**Request**:
```json
{
  "query": "What is the current Redis TTL?"
}
```

**Response**:
```json
{
  "query_analysis": { ... },
  "selection": {
    "ranked_sources": [
      {
        "source_id": "SRC-DOCS",
        "source_type": "document",
        "source_name": "Atlas Technical Documents",
        "query_relevance_score": 0.585,
        "authority_score": 0.900,
        "freshness_score": 0.812,
        "directness_score": 0.950,
        "weighted_score": 0.782,
        "selection_status": "SELECTED",
        "freshness_classification": "Query requires CURRENT configuration...",
        "score_explanation": "Prioritized (weighted score 0.782 >= 0.55) as authoritative source for current configuration..."
      }
    ],
    "selected_sources": [ ... ],
    "deprioritized_sources": [ ... ],
    "selection_threshold": 0.55,
    "maximum_selected_sources": 3,
    "unmet_information_requirements": [],
    "selection_summary": "Selected 1 source(s) [Atlas Technical Documents] exceeding threshold 0.55..."
  }
}
```

---

## 8. Configuration Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `API_PREFIX` | `str` | `/api/v1` | Base API route prefix |
| `WEIGHT_RELEVANCE` | `float` | `0.35` | Query relevance factor weight ($w_R$) |
| `WEIGHT_AUTHORITY` | `float` | `0.25` | Authority factor weight ($w_A$) |
| `WEIGHT_FRESHNESS` | `float` | `0.20` | Freshness factor weight ($w_F$) |
| `WEIGHT_DIRECTNESS` | `float` | `0.20` | Expected directness factor weight ($w_D$) |
| `SELECTION_THRESHOLD` | `float` | `0.55` | Minimum score threshold for selection |
| `MAX_SELECTED_SOURCES` | `int` | `3` | Maximum sources selected per query |
| `DATASET_AS_OF` | `str` | `2025-03-31T00:00:00Z` | Reference timestamp for Project Atlas |
| `FRESHNESS_HALF_LIFE_DAYS` | `float` | `180.0` | Half-life for recency decay calculation |

---

## 9. Testing & Validation

Run all unit and integration tests from `backend/`:

```bash
pytest -v
```

### Test Coverage Highlights:
- **`test_query_analysis.py`**: Tests A through G (Test A: Redis TTL; Test B: Redis why; Test C: Redis change over time; Test D: Auth architecture; Test E: API timeout fix; Test F: DB config comparison; Test G: Out of domain inquiry).
- **`test_source_scoring.py`**: Exact formula check ($0.9150$), bounds $[0.0, 1.0]$, weight sum validation, tie-breaking.
- **`test_source_selection.py`**: All 10 policy scenarios from Section 12.3.
- **`test_architecture_boundaries.py`**: Asserts zero calls to Qdrant, zero chunk text loading, zero BM25, zero LLM answer generation.
- **`test_query_api.py`**: FastAPI endpoint validation, response schemas, and 422 error handling.
- **`test_pipeline.py`, `test_documents.py`, `test_conversations_tickets.py`**: Retains 100% Phase 1 and Phase 2 compatibility.

---

## 10. Known Limitations

1. **Static Authority Mapping**: Authority weights are currently heuristic and source-type based. Phase 4 and Phase 5 can refine record-level authority dynamically.
2. **Cold Start Embeddings**: If `sentence-transformers` is used, the initial call has a minor latency overhead to load the local embedding model into memory.
3. **Controlled Scope**: External SaaS connectors (Notion, GitHub, Slack, Jira) are scheduled for subsequent iterations; current registry models Project Atlas documents, conversations, and tickets.

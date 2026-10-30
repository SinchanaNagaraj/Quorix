# Quorix REST API Specification

Quorix provides a high-performance REST API built on FastAPI. Base routes are prefixed with `/api/v1`.

---

## 1. System Health

### GET `/api/v1/health`
Returns system operational status and service component health.

**Response**:
```json
{
  "status": "ok",
  "app": "Quorix",
  "environment": "development"
}
```

---

## 2. Phase 3: Query Analysis & Intelligent Source Selection

### POST `/api/v1/query/analyze`
Analyzes a user's natural language question, identifying structured intent, temporal requirements, technical keywords, and information requirements. Operates via Gemini when configured, or deterministic rule-based fallback.

**Request**:
```json
{
  "query": "What is our current authentication configuration?"
}
```

**Response**:
```json
{
  "query_analysis": {
    "original_query": "What is our current authentication configuration?",
    "normalized_query": "what is our current authentication configuration",
    "primary_intent": "CONFIGURATION_LOOKUP",
    "secondary_intents": ["FACTUAL_LOOKUP"],
    "entities": ["authentication"],
    "technical_keywords": ["our", "current", "authentication", "configuration"],
    "information_requirements": [
      "Information on current configuration for authentication"
    ],
    "temporal_requirement": "CURRENT",
    "expected_information_categories": [
      "CURRENT_CONFIGURATION"
    ],
    "potential_source_types": [
      "document",
      "ticket"
    ],
    "requires_multiple_sources": false,
    "analysis_explanation": "Query evaluated as CONFIGURATION_LOOKUP with temporal requirement CURRENT. Key entities: ['authentication']. Expected information: ['CURRENT_CONFIGURATION'].",
    "analysis_method": "deterministic",
    "temporal_anchor": null
  }
}
```

---

### POST `/api/v1/query/select-sources`
Performs pre-retrieval routing: analyzes the query, scores all registered knowledge sources across 4 standardized dimensions ($R, A, F, D$), and selects candidate sources within configured budget and threshold limits.

**Request**:
```json
{
  "query": "What changed between the old and current authentication architecture?"
}
```

**Response**:
```json
{
  "query_analysis": {
    "original_query": "What changed between the old and current authentication architecture?",
    "normalized_query": "what changed between the old and current authentication architecture",
    "primary_intent": "COMPARISON",
    "secondary_intents": ["CHANGE_ANALYSIS"],
    "entities": ["authentication"],
    "technical_keywords": ["changed", "between", "old", "current", "authentication", "architecture"],
    "information_requirements": [
      "Information on historical reasoning for authentication",
      "Information on current configuration for authentication"
    ],
    "temporal_requirement": "COMPARATIVE",
    "expected_information_categories": [
      "HISTORICAL_REASONING",
      "CURRENT_CONFIGURATION"
    ],
    "potential_source_types": ["document", "ticket", "conversation"],
    "requires_multiple_sources": true,
    "analysis_explanation": "Query evaluated as COMPARISON with temporal requirement COMPARATIVE. Key entities: ['authentication'].",
    "analysis_method": "deterministic",
    "temporal_anchor": null
  },
  "selection": {
    "ranked_sources": [
      {
        "source_id": "SRC-DOCS",
        "source_type": "document",
        "source_name": "Atlas Technical Documents",
        "query_relevance_score": 0.8000,
        "authority_score": 0.9000,
        "freshness_score": 0.8800,
        "directness_score": 0.8500,
        "weighted_score": 0.8415,
        "selection_status": "SELECTED",
        "freshness_classification": "Query is COMPARATIVE; source documents established baseline specifications.",
        "score_explanation": "Selected (weighted score 0.842 >= 0.55) for comparative analysis; contributes relevance (0.80) and freshness (0.88) across time periods.",
        "relevance_breakdown": {
          "semantic_score": 0.5000,
          "category_score": 1.0000,
          "intent_score": 0.8500,
          "entity_score": 0.0000,
          "potential_source_boost": 0.1000,
          "total_score": 0.8000
        }
      },
      {
        "source_id": "SRC-CONV",
        "source_type": "conversation",
        "source_name": "Atlas Engineering Conversations",
        "query_relevance_score": 0.7500,
        "authority_score": 0.6250,
        "freshness_score": 0.9200,
        "directness_score": 0.8500,
        "weighted_score": 0.7516,
        "selection_status": "SELECTED",
        "freshness_classification": "Query is COMPARATIVE; source documents transition discussions, change history, or version rationale.",
        "score_explanation": "Selected (weighted score 0.752 >= 0.55) for comparative analysis; contributes relevance (0.75) and freshness (0.92) across time periods.",
        "relevance_breakdown": {
          "semantic_score": 0.5000,
          "category_score": 0.5000,
          "intent_score": 0.8500,
          "entity_score": 1.0000,
          "potential_source_boost": 0.1000,
          "total_score": 0.7500
        }
      }
    ],
    "selected_sources": [ ... ],
    "deprioritized_sources": [ ... ],
    "selection_threshold": 0.55,
    "maximum_selected_sources": 3,
    "temporal_coverage": {
      "historical": true,
      "current": true
    },
    "information_requirement_coverage": {
      "Information on historical reasoning for authentication": "SRC-CONV",
      "Information on current configuration for authentication": "SRC-DOCS"
    },
    "unmet_information_requirements": [],
    "selection_summary": "Selected 2 source(s) [Atlas Technical Documents, Atlas Engineering Conversations] exceeding threshold 0.55 (budget: 3). All 2 information requirements covered."
  }
}
```

"""Unit tests for Domain Vocabulary and Entity Alias Mapping (Fix 5).

Verifies:
- Configurable domain vocabulary.
- Entity alias normalization (e.g. postgres -> PostgreSQL, auth -> authentication).
- Technical synonyms expansion.
- Offline deterministic fallback operational without Gemini.
"""
import pytest

from app.intelligence.query_analysis.fallback import (
    analyze_query_deterministically,
    extract_entities,
    extract_temporal_anchor,
)
from app.intelligence.query_analysis.schemas import QueryIntent, TemporalRequirement
from app.intelligence.query_analysis.vocabulary import DomainVocabulary


def test_entity_alias_normalization():
    """Aliases like postgres, auth, db, pr normalize to canonical entities."""
    query = "How is postgres and auth configured in the pr workflow?"
    entities = extract_entities(query)

    assert "PostgreSQL" in entities
    assert "authentication" in entities
    assert "pull request" in entities


def test_custom_domain_vocabulary_injection():
    """Query analysis works with custom injected domain vocabulary."""
    custom_vocab = DomainVocabulary(
        known_entities=["Kubernetes", "GraphQL", "Snowflake"],
        entity_aliases={"k8s": "Kubernetes", "gql": "GraphQL"},
    )

    query = "Explain k8s pod scheduling architecture"
    analysis = analyze_query_deterministically(query, vocabulary=custom_vocab)

    assert "Kubernetes" in analysis.entities
    assert analysis.primary_intent == QueryIntent.TECHNICAL_EXPLANATION
    assert analysis.analysis_method == "deterministic"


def test_temporal_anchor_extraction():
    """Extracts explicit dates, years, and events as temporal anchors."""
    assert extract_temporal_anchor("What caused the August 2024 outage?") == "August 2024"
    assert extract_temporal_anchor("Compare the 2023 design with today") == "2023"
    assert extract_temporal_anchor("What is the current Redis TTL?") is None


def test_offline_deterministic_fallback():
    """Analyzer functions completely offline with zero LLM requirements."""
    analysis = analyze_query_deterministically("What is the current Redis TTL?")
    assert analysis.primary_intent == QueryIntent.CONFIGURATION_LOOKUP
    assert analysis.temporal_requirement == TemporalRequirement.CURRENT
    assert "Redis" in analysis.entities
    assert "TTL" in analysis.entities
    assert analysis.analysis_method == "deterministic"

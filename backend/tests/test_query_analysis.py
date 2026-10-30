"""Unit tests for Query Analysis Engine (Module A).

Covers Tests A through G as specified in PRD Section 12.1.
"""
import pytest

from app.intelligence.query_analysis.analyzer import QueryAnalyzer
from app.intelligence.query_analysis.fallback import analyze_query_deterministically
from app.intelligence.query_analysis.schemas import (
    InformationCategory,
    QueryIntent,
    TemporalRequirement,
)
from app.schemas.source import SourceType


@pytest.fixture
def analyzer():
    # Force deterministic analyzer for reproducible unit tests
    return QueryAnalyzer(gemini_api_key=None)


def test_query_a_current_redis_ttl(analyzer):
    """Test A: 'What is the current Redis TTL?'"""
    res = analyzer.analyze("What is the current Redis TTL?")
    assert res.primary_intent == QueryIntent.CONFIGURATION_LOOKUP
    assert res.temporal_requirement == TemporalRequirement.CURRENT
    assert any("redis" in e.lower() for e in res.entities)
    assert any("ttl" in e.lower() for e in res.entities)
    assert InformationCategory.CURRENT_CONFIGURATION in res.expected_information_categories
    assert SourceType.DOCUMENT in res.potential_source_types


def test_query_b_why_redis_caching_introduced(analyzer):
    """Test B: 'Why was Redis caching introduced?'"""
    res = analyzer.analyze("Why was Redis caching introduced?")
    assert res.primary_intent in (QueryIntent.HISTORICAL_REASONING, QueryIntent.DECISION_HISTORY)
    assert res.temporal_requirement == TemporalRequirement.HISTORICAL
    assert any("redis" in e.lower() for e in res.entities)
    assert any("caching" in e.lower() or "cache" in e.lower() for e in res.entities)
    assert SourceType.CONVERSATION in res.potential_source_types


def test_query_c_how_redis_config_changed_over_time(analyzer):
    """Test C: 'How has the Redis configuration changed over time?'"""
    res = analyzer.analyze("How has the Redis configuration changed over time?")
    assert res.temporal_requirement == TemporalRequirement.COMPARATIVE
    assert res.requires_multiple_sources is True
    assert any(
        cat in res.expected_information_categories
        for cat in (InformationCategory.HISTORICAL_REASONING, InformationCategory.CURRENT_CONFIGURATION)
    )


def test_query_d_explain_authentication_architecture(analyzer):
    """Test D: 'Explain the authentication architecture.'"""
    res = analyzer.analyze("Explain the authentication architecture.")
    assert res.primary_intent == QueryIntent.TECHNICAL_EXPLANATION
    assert any("auth" in e.lower() for e in res.entities)
    assert InformationCategory.ARCHITECTURE in res.expected_information_categories
    assert res.temporal_requirement == TemporalRequirement.TIME_INDEPENDENT
    assert SourceType.DOCUMENT in res.potential_source_types


def test_query_e_api_timeout_troubleshooting(analyzer):
    """Test E: 'Which issue caused the API timeout and how was it fixed?'"""
    res = analyzer.analyze("Which issue caused the API timeout and how was it fixed?")
    assert res.primary_intent == QueryIntent.TROUBLESHOOTING
    assert any(st in res.potential_source_types for st in (SourceType.TICKET, SourceType.CONVERSATION))
    assert any(
        cat in res.expected_information_categories
        for cat in (InformationCategory.TROUBLESHOOTING, InformationCategory.BUG_RESOLUTION)
    )


def test_query_f_compare_old_and_new_database(analyzer):
    """Test F: 'Compare the old and new database configurations.'"""
    res = analyzer.analyze("Compare the old and new database configurations.")
    assert res.primary_intent in (QueryIntent.COMPARISON, QueryIntent.CHANGE_ANALYSIS)
    assert res.temporal_requirement == TemporalRequirement.COMPARATIVE
    assert res.requires_multiple_sources is True


def test_query_g_out_of_domain_query(analyzer):
    """Test G: 'Tell me something that is not present in Project Atlas.'"""
    res = analyzer.analyze("Tell me something that is not present in Project Atlas.")
    assert res.primary_intent == QueryIntent.GENERAL_INFORMATION
    assert len(res.entities) == 0  # No fabricated entities
    assert res.temporal_requirement == TemporalRequirement.TIME_INDEPENDENT


def test_multi_part_query_mixed_temporal(analyzer):
    """Multi-part question with mixed temporal requirements."""
    res = analyzer.analyze("Why was Redis caching introduced, and what is its current TTL configuration?")
    assert res.temporal_requirement == TemporalRequirement.MIXED
    assert res.requires_multiple_sources is True
    assert InformationCategory.HISTORICAL_REASONING in res.expected_information_categories
    assert InformationCategory.CURRENT_CONFIGURATION in res.expected_information_categories
    assert SourceType.CONVERSATION in res.potential_source_types
    assert SourceType.DOCUMENT in res.potential_source_types

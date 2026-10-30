"""Unit tests for Relevance Scorer (Fix 3).

Verifies:
- Inspectability of RelevanceBreakdown subscores.
- Normalization in [0.0, 1.0].
- Safe handling of empty metadata (empty description, empty categories, empty query entities).
- Avoidance of single entity dominating complete relevance score.
- Synonym expansion for related concepts (e.g. auth <-> authentication/jwt).
- Category overlap and intent alignment.
- Deterministic and reproducible calculations.
"""
import pytest

from app.intelligence.query_analysis.schemas import (
    InformationCategory,
    QueryAnalysis,
    QueryIntent,
    TemporalRequirement,
)
from app.intelligence.source_selection.schemas import RelevanceBreakdown, SourceProfile
from app.intelligence.source_selection.scorers.relevance import RelevanceScorer
from app.schemas.source import SourceType


@pytest.fixture
def scorer():
    return RelevanceScorer()


def _make_profile(
    source_id: str = "SRC-DOCS",
    source_type: SourceType = SourceType.DOCUMENT,
    name: str = "Atlas Technical Documents",
    desc: str = "Architecture, authentication, and caching specifications.",
    categories: list[str] | None = None,
    supported_queries: list[str] | None = None,
) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        source_type=source_type,
        source_name=name,
        source_description=desc,
        authority_level="OFFICIAL_TECHNICAL_DOCUMENTATION",
        authority_score=0.90,
        available_content_categories=categories or ["architecture", "security policy", "configuration values"],
        supported_query_categories=supported_queries or ["technical explanation", "current configuration lookup"],
    )


def _make_query_analysis(
    query: str = "What is the authentication configuration?",
    intent: QueryIntent = QueryIntent.CONFIGURATION_LOOKUP,
    entities: list[str] | None = None,
    categories: list[InformationCategory] | None = None,
    potential_sources: list[SourceType] | None = None,
) -> QueryAnalysis:
    return QueryAnalysis(
        original_query=query,
        normalized_query=query.lower(),
        primary_intent=intent,
        entities=entities if entities is not None else ["authentication"],
        technical_keywords=["authentication", "configuration"],
        information_requirements=["Information on authentication configuration"],
        temporal_requirement=TemporalRequirement.CURRENT,
        expected_information_categories=categories or [InformationCategory.CURRENT_CONFIGURATION],
        potential_source_types=potential_sources or [SourceType.DOCUMENT],
        analysis_explanation="Query requires configuration lookup",
    )


def test_relevance_breakdown_inspectability(scorer):
    """Relevance breakdown exposes normalized, inspectable subscores."""
    source = _make_profile()
    analysis = _make_query_analysis()

    breakdown = scorer.score_with_breakdown(analysis, source)
    assert isinstance(breakdown, RelevanceBreakdown)
    assert 0.0 <= breakdown.semantic_score <= 1.0
    assert 0.0 <= breakdown.category_score <= 1.0
    assert 0.0 <= breakdown.intent_score <= 1.0
    assert 0.0 <= breakdown.entity_score <= 1.0
    assert 0.0 <= breakdown.total_score <= 1.0
    assert scorer.score(analysis, source) == breakdown.total_score


def test_synonym_and_related_concept_matching(scorer):
    """Related wording ('auth' vs 'authentication', 'jwt') matches via synonyms."""
    source = _make_profile(
        desc="Technical documentation on authentication security and JWT tokens.",
        categories=["security policy"],
    )
    # Query uses abbreviation "auth" and "token"
    analysis = _make_query_analysis(
        query="Explain auth and token guidelines",
        intent=QueryIntent.TECHNICAL_EXPLANATION,
        entities=["auth"],
        categories=[InformationCategory.ARCHITECTURE],
    )
    breakdown = scorer.score_with_breakdown(analysis, source)

    # Semantic similarity subscore should successfully match via synonym expansion
    assert breakdown.semantic_score > 0.40
    assert breakdown.total_score > 0.50


def test_safe_handling_of_empty_metadata(scorer):
    """Completely empty source metadata does not raise exceptions or produce NaN."""
    empty_source = SourceProfile(
        source_id="SRC-EMPTY",
        source_type=SourceType.DOCUMENT,
        source_name="",
        source_description="",
        authority_level="UNKNOWN_AUTHORITY",
        authority_score=0.40,
        available_content_categories=[],
        supported_query_categories=[],
    )
    analysis = _make_query_analysis(entities=[], categories=[])

    breakdown = scorer.score_with_breakdown(analysis, empty_source)
    assert 0.0 <= breakdown.total_score <= 1.0
    assert not pytest.approx(breakdown.total_score) == float("nan")


def test_no_metadata_overlap_produces_low_score(scorer):
    """Completely unrelated query and source yields low relevance."""
    source = _make_profile(
        name="Billing and Invoicing",
        desc="Payment processing, Stripe webhooks, and invoice generation.",
        categories=["billing", "payments"],
        supported_queries=["billing inquiries"],
    )

    analysis = _make_query_analysis(
        query="How to configure Redis cluster replication?",
        intent=QueryIntent.CONFIGURATION_LOOKUP,
        entities=["Redis"],
        categories=[InformationCategory.CURRENT_CONFIGURATION],
    )
    breakdown = scorer.score_with_breakdown(analysis, source)
    assert breakdown.total_score < 0.50


def test_single_entity_does_not_dominate_score(scorer):
    """Matching 1 of 4 entities scores proportionally lower than matching all 4."""
    source = _make_profile(
        desc="Redis cache configuration and memory limits.",
    )
    # Query mentions 4 entities: Redis, PostgreSQL, Kafka, RabbitMQ
    analysis_multi = _make_query_analysis(
        query="Compare Redis, PostgreSQL, Kafka, and RabbitMQ",
        entities=["Redis", "PostgreSQL", "Kafka", "RabbitMQ"],
    )
    # Query mentions only 1 entity: Redis
    analysis_single = _make_query_analysis(
        query="Explain Redis cache",
        entities=["Redis"],
    )

    bd_multi = scorer.score_with_breakdown(analysis_multi, source)
    bd_single = scorer.score_with_breakdown(analysis_single, source)

    # Multi-entity query matching only 1 entity has lower entity coverage
    assert bd_multi.entity_score < bd_single.entity_score
    assert bd_multi.entity_score == 0.25
    assert bd_single.entity_score == 1.0


def test_deterministic_and_reproducible_scoring(scorer):
    """Same query and source profile produce identical scores across invocations."""
    source = _make_profile()
    analysis = _make_query_analysis()

    score1 = scorer.score(analysis, source)
    score2 = scorer.score(analysis, source)
    assert score1 == score2

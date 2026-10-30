"""Unit tests for Source Selection budget semantics and policies (Fix 4).

Verifies:
- Configured max_selected_sources strictly enforced.
- Support selecting multiple source profiles of the same type.
- Comparative and Mixed queries preserve both historical and current evidence.
- Unmet information requirements explicitly reported when budget is exceeded or source missing.
- Never silently claims all requirements covered when dropped.
- Deterministic tie-breaking by authority score then source_id.
"""
from datetime import datetime, timezone
import pytest

from app.intelligence.query_analysis.schemas import (
    InformationCategory,
    QueryAnalysis,
    QueryIntent,
    TemporalRequirement,
)
from app.intelligence.source_selection.config import SourceSelectionSettings
from app.intelligence.source_selection.schemas import SelectionStatus, SourceProfile
from app.intelligence.source_selection.selector import SourceSelector
from app.schemas.source import SourceType


@pytest.fixture
def base_sources():
    ref = datetime(2025, 3, 31, 0, 0, tzinfo=timezone.utc)
    return [
        SourceProfile(
            source_id="SRC-DOCS-ARCH",
            source_type=SourceType.DOCUMENT,
            source_name="Architecture Specifications",
            source_description="Core system architecture and design specifications.",
            authority_level="APPROVED_ARCHITECTURE",
            authority_score=1.0,
            last_updated_at=ref,
            available_content_categories=["architecture", "configuration values"],
            supported_query_categories=["technical explanation", "current configuration lookup"],
        ),
        SourceProfile(
            source_id="SRC-DOCS-RUNBOOK",
            source_type=SourceType.DOCUMENT,
            source_name="Deployment Runbooks",
            source_description="Operational procedures, runbooks, and rollback steps.",
            authority_level="OFFICIAL_TECHNICAL_DOCUMENTATION",
            authority_score=0.90,
            last_updated_at=ref,
            available_content_categories=["runbooks", "deployment"],
            supported_query_categories=["troubleshooting"],
        ),
        SourceProfile(
            source_id="SRC-CONV",
            source_type=SourceType.CONVERSATION,
            source_name="Atlas Engineering Conversations",
            source_description="Design debates, ADR rationale, and historical discussions.",
            authority_level="ENGINEERING_CONVERSATION",
            authority_score=0.70,
            last_updated_at=ref,
            available_content_categories=["decision rationale", "historical design reasoning"],
            supported_query_categories=["why was X decided", "historical context"],
        ),
        SourceProfile(
            source_id="SRC-TICKETS",
            source_type=SourceType.TICKET,
            source_name="Atlas Development Tickets",
            source_description="Bug reports, implementation tickets, and incident records.",
            authority_level="RESOLVED_DEVELOPMENT_TICKET",
            authority_score=0.85,
            last_updated_at=ref,
            available_content_categories=["bug resolution", "incident records", "what changed and when"],
            supported_query_categories=["troubleshooting", "when/what was changed"],
        ),
    ]


def test_strict_maximum_budget_enforcement(base_sources):
    """Setting max_selected_sources = 2 selects at most 2 sources even when 4 qualify."""
    settings = SourceSelectionSettings(
        max_selected_sources=2,
        selection_threshold=0.50,
        reference_date=datetime(2025, 3, 31, tzinfo=timezone.utc),
    )
    selector = SourceSelector(settings=settings)

    analysis = QueryAnalysis(
        original_query="Explain the architecture and deployment process",
        normalized_query="explain architecture deployment",
        primary_intent=QueryIntent.TECHNICAL_EXPLANATION,
        temporal_requirement=TemporalRequirement.TIME_INDEPENDENT,
        expected_information_categories=[InformationCategory.ARCHITECTURE],
        potential_source_types=[SourceType.DOCUMENT],
        analysis_explanation="Architecture inquiry",
    )

    result = selector.select_sources(analysis, available_sources=base_sources)
    assert len(result.selected_sources) == 2
    assert len(result.deprioritized_sources) == 2


def test_selects_multiple_source_profiles_of_same_type(base_sources):
    """Query needing architecture and runbooks can select multiple DOCUMENT source profiles."""
    settings = SourceSelectionSettings(
        max_selected_sources=3,
        selection_threshold=0.50,
        reference_date=datetime(2025, 3, 31, tzinfo=timezone.utc),
    )
    selector = SourceSelector(settings=settings)

    analysis = QueryAnalysis(
        original_query="Explain architecture and deployment runbook details",
        normalized_query="explain architecture deployment runbook",
        primary_intent=QueryIntent.TECHNICAL_EXPLANATION,
        temporal_requirement=TemporalRequirement.TIME_INDEPENDENT,
        expected_information_categories=[InformationCategory.ARCHITECTURE, InformationCategory.IMPLEMENTATION_DETAILS],
        potential_source_types=[SourceType.DOCUMENT],
        analysis_explanation="Architecture and deployment lookup",
    )

    result = selector.select_sources(analysis, available_sources=base_sources)
    doc_sources = [s for s in result.selected_sources if s.source_type == SourceType.DOCUMENT]
    # Both SRC-DOCS-ARCH and SRC-DOCS-RUNBOOK should be selected
    assert len(doc_sources) >= 2
    selected_ids = {s.source_id for s in doc_sources}
    assert "SRC-DOCS-ARCH" in selected_ids
    assert "SRC-DOCS-RUNBOOK" in selected_ids


def test_comparative_preserves_both_historical_and_current(base_sources):
    """Comparative query preserves both historical conversation and current documentation."""
    settings = SourceSelectionSettings(
        max_selected_sources=3,
        selection_threshold=0.50,
        reference_date=datetime(2025, 3, 31, tzinfo=timezone.utc),
    )
    selector = SourceSelector(settings=settings)

    analysis = QueryAnalysis(
        original_query="Compare old design rationale and current architecture",
        normalized_query="compare old design rationale current architecture",
        primary_intent=QueryIntent.COMPARISON,
        temporal_requirement=TemporalRequirement.COMPARATIVE,
        expected_information_categories=[InformationCategory.HISTORICAL_REASONING, InformationCategory.CURRENT_CONFIGURATION],
        potential_source_types=[SourceType.DOCUMENT, SourceType.CONVERSATION],
        requires_multiple_sources=True,
        analysis_explanation="Comparative architecture query",
    )

    result = selector.select_sources(analysis, available_sources=base_sources)
    assert result.temporal_coverage.get("historical") is True
    assert result.temporal_coverage.get("current") is True

    selected_types = {s.source_type for s in result.selected_sources}
    assert SourceType.CONVERSATION in selected_types
    assert SourceType.DOCUMENT in selected_types


def test_explicit_unmet_requirements_when_budget_too_small(base_sources):
    """If budget max_selected_sources=1 but query has multiple requirements, unmet is reported."""
    settings = SourceSelectionSettings(
        max_selected_sources=1,
        selection_threshold=0.50,
        reference_date=datetime(2025, 3, 31, tzinfo=timezone.utc),
    )
    selector = SourceSelector(settings=settings)

    analysis = QueryAnalysis(
        original_query="Why did we introduce caching, and what is the current configuration?",
        normalized_query="why introduce caching current configuration",
        primary_intent=QueryIntent.HISTORICAL_REASONING,
        secondary_intents=[QueryIntent.CONFIGURATION_LOOKUP],
        temporal_requirement=TemporalRequirement.MIXED,
        information_requirements=[
            "Information on historical reasoning for caching",
            "Information on current configuration for caching",
        ],
        expected_information_categories=[InformationCategory.HISTORICAL_REASONING, InformationCategory.CURRENT_CONFIGURATION],
        potential_source_types=[SourceType.CONVERSATION, SourceType.DOCUMENT],
        requires_multiple_sources=True,
        analysis_explanation="Mixed historical and configuration query",
    )

    result = selector.select_sources(analysis, available_sources=base_sources)
    assert len(result.selected_sources) == 1
    # One of the two distinct requirements must be reported as unmet
    assert len(result.unmet_information_requirements) >= 1
    assert "Warning" in result.selection_summary or "unmet" in result.selection_summary.lower()
    # Check that requirement coverage explicitly records "unmet"
    assert any(status == "unmet" for status in result.information_requirement_coverage.values())

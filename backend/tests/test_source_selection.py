"""Unit tests for Source Selection Policies, Ranking, and Explanations (Module B).

Covers all 10 verification scenarios required by PRD Section 12.3.
"""
import pytest

from app.intelligence.query_analysis.analyzer import QueryAnalyzer
from app.intelligence.source_selection.config import SourceSelectionSettings
from app.intelligence.source_selection.registry import SourceRegistry
from app.intelligence.source_selection.schemas import SelectionStatus
from app.intelligence.source_selection.selector import SourceSelector
from app.schemas.source import SourceType


@pytest.fixture
def analyzer():
    return QueryAnalyzer(gemini_api_key=None)


@pytest.fixture
def selector():
    return SourceSelector()


def test_scenario_1_historical_queries_prioritize_conversations(analyzer, selector):
    """Historical reasoning queries prioritize Engineering Conversations."""
    analysis = analyzer.analyze("Why was Redis caching introduced?")
    result = selector.select_sources(analysis)

    top_source = result.ranked_sources[0]
    assert top_source.source_type == SourceType.CONVERSATION
    assert top_source.selection_status == SelectionStatus.SELECTED
    assert "historical" in top_source.score_explanation.lower()


def test_scenario_2_current_config_prioritizes_documents(analyzer, selector):
    """Current configuration queries prioritize Technical Documents."""
    analysis = analyzer.analyze("What is the current Redis TTL?")
    result = selector.select_sources(analysis)

    top_source = result.ranked_sources[0]
    assert top_source.source_type == SourceType.DOCUMENT
    assert top_source.selection_status == SelectionStatus.SELECTED
    assert "configuration" in top_source.score_explanation.lower()


def test_scenario_3_comparative_queries_select_multiple_sources(analyzer, selector):
    """Comparative queries select multiple source categories."""
    analysis = analyzer.analyze("How has the Redis configuration changed over time?")
    result = selector.select_sources(analysis)

    assert len(result.selected_sources) >= 2
    selected_types = {s.source_type for s in result.selected_sources}
    assert SourceType.DOCUMENT in selected_types
    assert (SourceType.CONVERSATION in selected_types or SourceType.TICKET in selected_types)


def test_scenario_4_authority_influences_ranking(analyzer, selector):
    """Technical explanation query: Document authority (0.95) elevates it above casual chatter."""
    analysis = analyzer.analyze("Explain the authentication architecture.")
    result = selector.select_sources(analysis)

    doc_source = next(s for s in result.ranked_sources if s.source_type == SourceType.DOCUMENT)
    conv_source = next(s for s in result.ranked_sources if s.source_type == SourceType.CONVERSATION)
    assert doc_source.authority_score > conv_source.authority_score
    assert doc_source.weighted_score > conv_source.weighted_score


def test_scenario_5_freshness_changes_by_temporal_requirement(analyzer, selector):
    """Freshness behaves differently for CURRENT vs HISTORICAL queries."""
    current_analysis = analyzer.analyze("What is the current Redis TTL?")
    hist_analysis = analyzer.analyze("Why was Redis caching originally introduced?")

    current_res = selector.select_sources(current_analysis)
    hist_res = selector.select_sources(hist_analysis)

    conv_curr = next(s for s in current_res.ranked_sources if s.source_type == SourceType.CONVERSATION)
    conv_hist = next(s for s in hist_res.ranked_sources if s.source_type == SourceType.CONVERSATION)

    # In historical queries, conversations receive maximum historical freshness alignment (0.95)
    assert conv_hist.freshness_score >= conv_curr.freshness_score


def test_scenario_6_directness_affects_ranking_independently(analyzer, selector):
    """Directness measures answer immediacy; for troubleshooting, tickets directness > docs."""
    analysis = analyzer.analyze("Which issue caused the API timeout and how was it fixed?")
    result = selector.select_sources(analysis)

    ticket_source = next(s for s in result.ranked_sources if s.source_type == SourceType.TICKET)
    doc_source = next(s for s in result.ranked_sources if s.source_type == SourceType.DOCUMENT)

    assert ticket_source.directness_score > doc_source.directness_score


def test_scenario_7_not_all_sources_selected_arbitrarily(analyzer, selector):
    """Simple specific queries do NOT indiscriminately select all sources."""
    analysis = analyzer.analyze("Explain the authentication architecture.")
    result = selector.select_sources(analysis)

    # Conversations should be deprioritized for pure architecture doc lookup
    assert any(s.selection_status == SelectionStatus.DEPRIORITIZED for s in result.ranked_sources)


def test_scenario_8_source_below_threshold_is_deprioritized(analyzer):
    """Sources below selection threshold are marked DEPRIORITIZED."""
    custom_settings = SourceSelectionSettings(selection_threshold=0.88)
    high_threshold_selector = SourceSelector(settings=custom_settings)

    analysis = analyzer.analyze("What is the current Redis TTL?")
    result = high_threshold_selector.select_sources(analysis)

    for dep in result.deprioritized_sources:
        assert dep.selection_status in (SelectionStatus.DEPRIORITIZED, SelectionStatus.NO_SUITABLE_SOURCE)
        assert dep.weighted_score < 0.88 or len(result.selected_sources) >= 3


def test_scenario_9_no_suitable_source_when_none_qualifies(analyzer):
    """When no source meets threshold (e.g. threshold 0.99 or off-topic), returns NO_SUITABLE_SOURCE."""
    strict_settings = SourceSelectionSettings(selection_threshold=0.99)
    strict_selector = SourceSelector(settings=strict_settings)

    analysis = analyzer.analyze("Tell me something that is not present in Project Atlas.")
    result = strict_selector.select_sources(analysis)

    assert len(result.selected_sources) == 0
    assert "NO_SUITABLE_SOURCE" in result.selection_summary
    assert all(s.selection_status == SelectionStatus.NO_SUITABLE_SOURCE for s in result.ranked_sources)


def test_scenario_10_selection_reproducible_for_identical_inputs(analyzer, selector):
    """Source selection is completely deterministic given identical inputs."""
    analysis1 = analyzer.analyze("Why was Redis caching introduced, and what is its current TTL configuration?")
    analysis2 = analyzer.analyze("Why was Redis caching introduced, and what is its current TTL configuration?")

    res1 = selector.select_sources(analysis1)
    res2 = selector.select_sources(analysis2)

    assert [s.source_id for s in res1.ranked_sources] == [s.source_id for s in res2.ranked_sources]
    assert [s.weighted_score for s in res1.ranked_sources] == [s.weighted_score for s in res2.ranked_sources]
    assert [s.selection_status for s in res1.ranked_sources] == [s.selection_status for s in res2.ranked_sources]
    assert res1.selection_summary == res2.selection_summary

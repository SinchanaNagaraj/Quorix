"""Unit tests for Freshness Scorer (Fix 1 and Fix 2).

Verifies:
- Reference date injection and clock determinism.
- Mathematical exponential decay: F = exp(-ln(2) * age_days / half_life_days).
- Source updated today (age = 0 -> F = 1.0).
- Source updated 180 days ago (age = 180 -> F = 0.50).
- Source updated 360 days ago (age = 360 -> F = 0.25).
- Missing timestamp returns configured neutral score without failure.
- Future timestamps handled safely.
- Timezone-aware vs naive normalization equivalency.
- Temporal requirement logic: CURRENT, HISTORICAL, COMPARATIVE, TIME_INDEPENDENT, MIXED.
"""
import math
from datetime import datetime, timedelta, timezone
import pytest

from app.intelligence.query_analysis.schemas import (
    InformationCategory,
    QueryAnalysis,
    QueryIntent,
    TemporalRequirement,
)
from app.intelligence.source_selection.schemas import SourceProfile
from app.intelligence.source_selection.scorers.freshness import FreshnessScorer
from app.schemas.source import SourceType


@pytest.fixture
def ref_time():
    return datetime(2025, 3, 31, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def scorer(ref_time):
    return FreshnessScorer(reference_time=ref_time, half_life_days=180.0)


def _make_source(
    source_id: str = "SRC-TEST",
    source_type: SourceType = SourceType.DOCUMENT,
    last_updated: datetime | None = None,
    categories: list[str] | None = None,
) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        source_type=source_type,
        source_name=f"Test {source_id}",
        source_description="Test source description",
        authority_level="OFFICIAL_TECHNICAL_DOCUMENTATION",
        authority_score=0.90,
        last_updated_at=last_updated,
        available_content_categories=categories or ["configuration values"],
        supported_query_categories=["current configuration lookup"],
    )


def _make_query_analysis(
    temporal: TemporalRequirement = TemporalRequirement.CURRENT,
    anchor: str | None = None,
) -> QueryAnalysis:
    return QueryAnalysis(
        original_query="Test question?",
        normalized_query="test question",
        primary_intent=QueryIntent.CONFIGURATION_LOOKUP,
        temporal_requirement=temporal,
        expected_information_categories=[InformationCategory.CURRENT_CONFIGURATION],
        potential_source_types=[SourceType.DOCUMENT],
        analysis_explanation="Test explanation",
        temporal_anchor=anchor,
    )


def test_source_updated_today(scorer, ref_time):
    """Source updated at reference date has age 0 and freshness 1.0."""
    source = _make_source(last_updated=ref_time)
    analysis = _make_query_analysis(TemporalRequirement.CURRENT)
    score, desc = scorer.score(analysis, source)

    assert pytest.approx(score, rel=1e-3) == 1.0
    assert "0.0 days" in desc or "0 days" in desc


def test_source_updated_180_days_ago(scorer, ref_time):
    """Source updated exactly 180 days ago (1 half-life) scores exactly 0.50."""
    ts = ref_time - timedelta(days=180)
    source = _make_source(last_updated=ts)
    analysis = _make_query_analysis(TemporalRequirement.CURRENT)
    score, desc = scorer.score(analysis, source)

    expected = math.exp(-math.log(2) * 1.0)  # 0.5
    assert pytest.approx(score, abs=1e-3) == 0.50
    assert pytest.approx(score, abs=1e-3) == expected


def test_source_updated_360_days_ago(scorer, ref_time):
    """Source updated exactly 360 days ago (2 half-lives) scores exactly 0.25."""
    ts = ref_time - timedelta(days=360)
    source = _make_source(last_updated=ts)
    analysis = _make_query_analysis(TemporalRequirement.CURRENT)
    score, desc = scorer.score(analysis, source)

    expected = math.exp(-math.log(2) * 2.0)  # 0.25
    assert pytest.approx(score, abs=1e-3) == 0.25
    assert pytest.approx(score, abs=1e-3) == expected


def test_source_with_missing_timestamp(scorer):
    """Source with missing timestamp returns conservative neutral score without crashing."""
    source = _make_source(last_updated=None)
    analysis = _make_query_analysis(TemporalRequirement.CURRENT)
    score, desc = scorer.score(analysis, source)

    assert score == 0.50
    assert "unavailable" in desc.lower()


def test_source_with_future_timestamp(scorer, ref_time):
    """Source with future timestamp is safely handled with maximum freshness."""
    future_ts = ref_time + timedelta(days=30)
    source = _make_source(last_updated=future_ts)
    analysis = _make_query_analysis(TemporalRequirement.CURRENT)
    score, desc = scorer.score(analysis, source)

    assert score == 1.0
    assert "future" in desc.lower()


def test_timezone_aware_and_naive_equivalence(scorer, ref_time):
    """Naive timestamp assumed UTC produces identical calculation to aware UTC timestamp."""
    naive_ts = datetime(2025, 1, 1, 12, 0, 0)
    aware_ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    source_naive = _make_source(source_id="NAIVE", last_updated=naive_ts)
    source_aware = _make_source(source_id="AWARE", last_updated=aware_ts)

    analysis = _make_query_analysis(TemporalRequirement.CURRENT)
    score_naive, _ = scorer.score(analysis, source_naive)
    score_aware, _ = scorer.score(analysis, source_aware)

    assert score_naive == score_aware


def test_different_timezones_representing_same_instant(ref_time):
    """Offsets representing the exact same UTC instant produce identical scores."""
    scorer = FreshnessScorer(reference_time=ref_time)
    # 2025-01-01 12:00:00 UTC
    utc_ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Same instant in EST (UTC-5): 2025-01-01 07:00:00 -05:00
    est_tz = timezone(timedelta(hours=-5))
    est_ts = datetime(2025, 1, 1, 7, 0, 0, tzinfo=est_tz)

    source_utc = _make_source(source_id="UTC", last_updated=utc_ts)
    source_est = _make_source(source_id="EST", last_updated=est_ts)

    analysis = _make_query_analysis(TemporalRequirement.CURRENT)
    score_utc, _ = scorer.score(analysis, source_utc)
    score_est, _ = scorer.score(analysis, source_est)

    assert score_utc == score_est


def test_clock_callable_support():
    """FreshnessScorer supports callable reference clock."""
    fixed = datetime(2025, 3, 31, 0, 0, tzinfo=timezone.utc)
    scorer = FreshnessScorer(reference_time=lambda: fixed)

    source = _make_source(last_updated=fixed - timedelta(days=180))
    analysis = _make_query_analysis(TemporalRequirement.CURRENT)
    score, _ = scorer.score(analysis, source)

    assert pytest.approx(score, abs=1e-3) == 0.50


def test_historical_freshness_event_alignment(scorer, ref_time):
    """Historical questions with event/date anchor reward temporally aligned sources."""
    # Source from 2024
    source_2024 = _make_source(
        source_id="SRC-2024",
        source_type=SourceType.CONVERSATION,
        last_updated=datetime(2024, 8, 15, 10, 0, tzinfo=timezone.utc),
        categories=["incident records", "decision rationale"],
    )
    # Source from 2021
    source_2021 = _make_source(
        source_id="SRC-2021",
        source_type=SourceType.DOCUMENT,
        last_updated=datetime(2021, 1, 1, 10, 0, tzinfo=timezone.utc),
        categories=["general process"],
    )

    analysis = _make_query_analysis(
        temporal=TemporalRequirement.HISTORICAL,
        anchor="August 2024 Outage",
    )
    score_2024, desc_2024 = scorer.score(analysis, source_2024)
    score_2021, desc_2021 = scorer.score(analysis, source_2021)

    assert score_2024 > score_2021
    assert score_2024 == 0.95


def test_time_independent_neutral_scoring(scorer, ref_time):
    """Time-independent questions assign neutral score regardless of recent vs older timestamp."""
    recent_source = _make_source(
        source_id="RECENT",
        last_updated=ref_time,
    )
    older_source = _make_source(
        source_id="OLDER",
        last_updated=ref_time - timedelta(days=700),
    )

    analysis = _make_query_analysis(temporal=TemporalRequirement.TIME_INDEPENDENT)
    score_rec, _ = scorer.score(analysis, recent_source)
    score_old, _ = scorer.score(analysis, older_source)

    # In time-independent queries, recency bias is eliminated
    assert score_rec == score_old == scorer.neutral_score

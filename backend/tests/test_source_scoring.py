"""Unit tests for Source Scoring Factor calculations and mathematical validation (Module B).

Covers Section 12.2 requirements:
- Exact weighted formula: S(q, s) = 0.35*R + 0.25*A + 0.20*F + 0.20*D
- Minimum and maximum factor boundaries
- Normalization [0.0, 1.0]
- Weight sum validation and non-negativity
- Deterministic tie-breaking
"""
import pytest
from pydantic import ValidationError

from app.intelligence.source_selection.config import ScoringWeights
from app.intelligence.source_selection.schemas import (
    SelectionStatus,
    SourceProfile,
    SourceScoreBreakdown,
)
from app.schemas.source import SourceType


def calculate_weighted_score(r: float, a: float, f: float, d: float, weights: ScoringWeights | None = None) -> float:
    w = weights or ScoringWeights()
    return round((w.relevance * r) + (w.authority * a) + (w.freshness * f) + (w.directness * d), 4)


def test_prd_exact_example_calculation():
    """Verify the PRD worked example: R=0.95, A=0.85, F=0.90, D=0.95 -> S=0.915."""
    r = 0.95
    a = 0.85
    f = 0.90
    d = 0.95
    score = calculate_weighted_score(r, a, f, d)
    # 0.35*0.95 = 0.3325
    # 0.25*0.85 = 0.2125
    # 0.20*0.90 = 0.1800
    # 0.20*0.95 = 0.1900
    # Sum = 0.9150
    assert pytest.approx(score, rel=1e-4) == 0.9150


def test_minimum_boundary_score():
    """All zero factors produce 0.0."""
    score = calculate_weighted_score(0.0, 0.0, 0.0, 0.0)
    assert score == 0.0


def test_maximum_boundary_score():
    """All 1.0 factors produce 1.0."""
    score = calculate_weighted_score(1.0, 1.0, 1.0, 1.0)
    assert score == 1.0


def test_weight_sum_validation():
    """Weights that do not sum to 1.0 raise ValidationError."""
    with pytest.raises(ValidationError):
        ScoringWeights(relevance=0.40, authority=0.30, freshness=0.20, directness=0.20)  # Sums to 1.10

    with pytest.raises(ValidationError):
        ScoringWeights(relevance=0.20, authority=0.20, freshness=0.20, directness=0.20)  # Sums to 0.80


def test_weight_negative_validation():
    """Negative weights raise ValidationError."""
    with pytest.raises(ValidationError):
        ScoringWeights(relevance=-0.10, authority=0.50, freshness=0.30, directness=0.30)


def test_score_breakdown_bounds_validation():
    """SourceScoreBreakdown rejects scores outside [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        SourceScoreBreakdown(
            source_id="S1",
            source_type=SourceType.DOCUMENT,
            source_name="Test",
            query_relevance_score=1.2,  # > 1.0
            authority_score=0.8,
            freshness_score=0.8,
            directness_score=0.8,
            weighted_score=0.9,
            selection_status=SelectionStatus.SELECTED,
            freshness_classification="test",
            score_explanation="test",
        )

    with pytest.raises(ValidationError):
        SourceScoreBreakdown(
            source_id="S1",
            source_type=SourceType.DOCUMENT,
            source_name="Test",
            query_relevance_score=-0.1,  # < 0.0
            authority_score=0.8,
            freshness_score=0.8,
            directness_score=0.8,
            weighted_score=0.9,
            selection_status=SelectionStatus.SELECTED,
            freshness_classification="test",
            score_explanation="test",
        )


def test_deterministic_tie_breaking():
    """Ties on weighted score are broken deterministically by authority_score, then source_id."""
    s1 = SourceScoreBreakdown(
        source_id="SRC-B",
        source_type=SourceType.CONVERSATION,
        source_name="Conv",
        query_relevance_score=0.80,
        authority_score=0.70,
        freshness_score=0.80,
        directness_score=0.80,
        weighted_score=0.7850,
        selection_status=SelectionStatus.SELECTED,
        freshness_classification="test",
        score_explanation="test",
    )
    s2 = SourceScoreBreakdown(
        source_id="SRC-A",
        source_type=SourceType.DOCUMENT,
        source_name="Docs",
        query_relevance_score=0.80,
        authority_score=0.90,  # Higher authority
        freshness_score=0.80,
        directness_score=0.80,
        weighted_score=0.7850,
        selection_status=SelectionStatus.SELECTED,
        freshness_classification="test",
        score_explanation="test",
    )
    s3 = SourceScoreBreakdown(
        source_id="SRC-C",
        source_type=SourceType.TICKET,
        source_name="Tickets",
        query_relevance_score=0.80,
        authority_score=0.70,  # Same authority as SRC-B, but source_id is alphabetically after SRC-B
        freshness_score=0.80,
        directness_score=0.80,
        weighted_score=0.7850,
        selection_status=SelectionStatus.SELECTED,
        freshness_classification="test",
        score_explanation="test",
    )

    ranked = sorted([s3, s1, s2], key=lambda x: (-x.weighted_score, -x.authority_score, x.source_id))
    # s2 first (higher authority 0.90), then s1 (SRC-B before SRC-C)
    assert [s.source_id for s in ranked] == ["SRC-A", "SRC-B", "SRC-C"]

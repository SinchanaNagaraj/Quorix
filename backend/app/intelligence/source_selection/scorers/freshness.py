"""Source Freshness Scorer (Factor F: 20%).

Evaluates source freshness in a query-dependent manner:
- CURRENT queries reward recent timestamps using configurable exponential decay:
    F = exp(-ln(2) * age_days / half_life_days)
- HISTORICAL queries reward sources temporally aligned with the historical event
    or documenting decision milestones, using neutral policies when period is unspecified.
- COMPARATIVE queries reward sources providing transition and baseline temporal coverage.
- TIME_INDEPENDENT queries receive stable, non-penalized neutral freshness.
- MIXED queries balance current recency decay with historical decision coverage.

Supports injectable reference clocks/dates, consistent UTC normalization,
safe handling of future and missing timestamps. Normalized to [0.0, 1.0].
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Callable

from app.intelligence.query_analysis.schemas import QueryAnalysis, TemporalRequirement
from app.intelligence.source_selection.schemas import SourceProfile
from app.schemas.source import SourceType


class FreshnessScorer:
    """Calculates query-dependent freshness score F and explanation."""

    def __init__(
        self,
        reference_time: datetime | Callable[[], datetime] | None = None,
        half_life_days: float = 180.0,
        missing_timestamp_score: float = 0.50,
        future_timestamp_score: float = 1.0,
        neutral_score: float = 0.75,
        neutral_historical_score: float = 0.70,
    ) -> None:
        self.reference_time = reference_time
        self.half_life_days = half_life_days
        self.missing_timestamp_score = missing_timestamp_score
        self.future_timestamp_score = future_timestamp_score
        self.neutral_score = neutral_score
        self.neutral_historical_score = neutral_historical_score

    def get_reference_time(self) -> datetime:
        """Resolve the effective reference time as UTC datetime."""
        if callable(self.reference_time):
            ref = self.reference_time()
        elif isinstance(self.reference_time, datetime):
            ref = self.reference_time
        else:
            ref = datetime.now(timezone.utc)

        if ref.tzinfo is None:
            return ref.replace(tzinfo=timezone.utc)
        return ref.astimezone(timezone.utc)

    def score(
        self, query_analysis: QueryAnalysis, source: SourceProfile
    ) -> tuple[float, str]:
        """Calculate normalized freshness score in [0.0, 1.0] and freshness explanation."""
        ts = source.last_updated_at
        if ts is None:
            return (
                self.missing_timestamp_score,
                f"Timestamp unavailable in source metadata; assigned conservative score ({self.missing_timestamp_score:.2f}).",
            )

        # Normalize source timestamp to UTC
        if ts.tzinfo is None:
            ts_utc = ts.replace(tzinfo=timezone.utc)
        else:
            ts_utc = ts.astimezone(timezone.utc)

        ref_utc = self.get_reference_time()
        delta_seconds = (ref_utc - ts_utc).total_seconds()
        age_days = delta_seconds / 86400.0

        # Safe handling of future timestamps (clock skew or future scheduled revisions)
        if age_days < 0.0:
            explanation = (
                f"Source timestamp ({ts_utc.isoformat()}) is in the future relative to "
                f"reference time ({ref_utc.isoformat()}); treated safely with maximum freshness."
            )
            return round(self.future_timestamp_score, 4), explanation

        temporal = query_analysis.temporal_requirement

        if temporal == TemporalRequirement.CURRENT:
            # Pure exponential decay: F = exp(-ln(2) * age_days / half_life_days)
            # age = 0 -> 1.0; age = half_life -> 0.5; age = 2*half_life -> 0.25
            decay = math.exp(-math.log(2) * (age_days / self.half_life_days))
            score = max(0.0, min(1.0, decay))
            explanation = (
                f"Query requires CURRENT state. Source updated {age_days:.1f} days "
                f"prior to reference date ({ts_utc.date()}); exponential decay score: {score:.4f}."
            )

        elif temporal == TemporalRequirement.HISTORICAL:
            # Evaluate temporal alignment with the historical event
            source_cats = [c.lower() for c in source.available_content_categories + source.supported_query_categories]
            has_decision_records = any("decision" in c or "rationale" in c or "historical" in c for c in source_cats)

            # Check if query has a specific historical date anchor (e.g. "2024", "August 2024", "outage")
            if query_analysis.temporal_anchor:
                anchor = query_analysis.temporal_anchor.lower()
                year_match = next((tok for tok in anchor.split() if tok.isdigit() and len(tok) == 4), None)
                if year_match and ts_utc.year == int(year_match):
                    score = 0.95
                    explanation = (
                        f"Query seeks HISTORICAL event around {query_analysis.temporal_anchor}; "
                        f"source timestamp ({ts_utc.year}) is directly aligned."
                    )
                elif "outage" in anchor and any("incident" in c or "outage" in c or "post-mortem" in c for c in source_cats):
                    score = 0.95
                    explanation = f"Query references incident/outage; source directly indexes incident records."
                elif has_decision_records:
                    score = 0.85
                    explanation = f"Query seeks HISTORICAL context; source documents relevant decision rationale."
                else:
                    score = self.neutral_historical_score
                    explanation = f"Query seeks HISTORICAL event; source provides background context ({score:.2f})."
            elif has_decision_records or source.source_type == SourceType.CONVERSATION:
                score = 0.95
                explanation = "Query seeks HISTORICAL reasoning; engineering conversation and decision history is temporally relevant."
            elif source.source_type == SourceType.TICKET:
                score = 0.90
                explanation = "Query seeks HISTORICAL context; development ticket records capture historical resolution notes."
            else:
                score = self.neutral_historical_score
                explanation = f"Query seeks HISTORICAL context; source provides neutral historical documentation coverage ({score:.2f})."

        elif temporal == TemporalRequirement.COMPARATIVE:
            # Comparative queries need both historical transition evidence and current baselines
            source_cats = [c.lower() for c in source.available_content_categories]
            if any("decision" in c or "rationale" in c or "change" in c for c in source_cats) or source.source_type in (
                SourceType.CONVERSATION,
                SourceType.TICKET,
            ):
                score = 0.92
                explanation = "Query is COMPARATIVE; source documents transition discussions, change history, or version rationale."
            else:
                score = 0.88
                explanation = "Query is COMPARATIVE; source documents established baseline specifications."

        elif temporal == TemporalRequirement.MIXED:
            # Mixed query: blend current recency decay with historical relevance
            decay = math.exp(-math.log(2) * (age_days / self.half_life_days))
            source_cats = [c.lower() for c in source.available_content_categories]
            has_hist = any("decision" in c or "rationale" in c for c in source_cats) or source.source_type in (
                SourceType.CONVERSATION,
                SourceType.TICKET,
            )
            hist_component = 0.92 if has_hist else 0.75
            score = 0.5 * decay + 0.5 * hist_component
            explanation = (
                f"Query has MIXED temporal requirements; blended recency ({decay:.2f}) "
                f"and historical coverage ({hist_component:.2f}) -> {score:.4f}."
            )

        else:  # TIME_INDEPENDENT
            score = self.neutral_score
            explanation = (
                f"Query is TIME_INDEPENDENT; freshness penalty waived for foundational "
                f"architecture/concepts (neutral score: {score:.2f})."
            )

        normalized = max(0.0, min(1.0, score))
        return round(normalized, 4), explanation

"""Intelligent Source Selection Engine.

Evaluates knowledge sources before retrieving their contents, scoring them across
Relevance (35%), Authority (25%), Freshness (20%), and Expected Directness (20%),
and enforcing configurable selection policies.
"""
from __future__ import annotations

import logging
import time
from typing import Sequence

from app.intelligence.query_analysis.schemas import QueryAnalysis, QueryIntent, TemporalRequirement
from app.intelligence.source_selection.config import SourceSelectionSettings
from app.intelligence.source_selection.explanation import generate_source_explanation
from app.intelligence.source_selection.registry import SourceRegistry
from app.intelligence.source_selection.schemas import (
    SelectionStatus,
    SourceProfile,
    SourceScoreBreakdown,
    SourceSelectionResult,
)
from app.intelligence.source_selection.scorers.authority import AuthorityScorer
from app.intelligence.source_selection.scorers.directness import DirectnessScorer
from app.intelligence.source_selection.scorers.freshness import FreshnessScorer
from app.intelligence.source_selection.scorers.relevance import RelevanceScorer
from app.schemas.source import SourceType

log = logging.getLogger(__name__)


class SourceSelector:
    """Orchestrates source evaluation, factor scoring, ranking, and explainable selection."""

    def __init__(
        self,
        settings: SourceSelectionSettings | None = None,
        registry: SourceRegistry | None = None,
        relevance_scorer: RelevanceScorer | None = None,
        authority_scorer: AuthorityScorer | None = None,
        freshness_scorer: FreshnessScorer | None = None,
        directness_scorer: DirectnessScorer | None = None,
    ) -> None:
        self.settings = settings or SourceSelectionSettings.from_app_settings()
        self.registry = registry or SourceRegistry()
        self.relevance_scorer = relevance_scorer or RelevanceScorer()
        self.authority_scorer = authority_scorer or AuthorityScorer()
        self.freshness_scorer = freshness_scorer or FreshnessScorer(
            reference_time=self.settings.reference_date or self.settings.dataset_as_of,
            half_life_days=self.settings.freshness_half_life_days,
            missing_timestamp_score=self.settings.missing_timestamp_score,
            future_timestamp_score=self.settings.future_timestamp_score,
            neutral_score=self.settings.neutral_temporal_score,
        )
        self.directness_scorer = directness_scorer or DirectnessScorer()

    def select_sources(
        self,
        query_analysis: QueryAnalysis,
        available_sources: Sequence[SourceProfile] | None = None,
    ) -> SourceSelectionResult:
        """Evaluate and rank available sources for a structured query analysis."""
        start_time = time.perf_counter()
        log.info("Source scoring started for query: %r", query_analysis.original_query)

        sources = list(available_sources or self.registry.get_all_sources())
        w = self.settings.weights
        threshold = self.settings.selection_threshold
        max_sources = self.settings.max_selected_sources

        scored_sources: list[SourceScoreBreakdown] = []

        for src in sources:
            r_breakdown = self.relevance_scorer.score_with_breakdown(query_analysis, src)
            r = r_breakdown.total_score
            a = self.authority_scorer.score(src)
            f, fresh_desc = self.freshness_scorer.score(query_analysis, src)
            d = self.directness_scorer.score(query_analysis, src)

            # Central formula: S(q, s) = (0.35 * R) + (0.25 * A) + (0.20 * F) + (0.20 * D)
            weighted = (w.relevance * r) + (w.authority * a) + (w.freshness * f) + (w.directness * d)
            weighted_score = round(max(0.0, min(1.0, weighted)), 4)

            log.debug(
                "Source %s scored: R=%.3f, A=%.3f, F=%.3f, D=%.3f -> Weighted=%.4f",
                src.source_id, r, a, f, d, weighted_score,
            )

            scored_sources.append(
                SourceScoreBreakdown(
                    source_id=src.source_id,
                    source_type=src.source_type,
                    source_name=src.source_name,
                    query_relevance_score=r,
                    authority_score=a,
                    freshness_score=f,
                    directness_score=d,
                    weighted_score=weighted_score,
                    selection_status=SelectionStatus.DEPRIORITIZED,  # Assigned below
                    freshness_classification=fresh_desc,
                    score_explanation="",  # Generated below
                    relevance_breakdown=r_breakdown,
                )
            )

        # Deterministic sorting: weighted_score DESC, authority_score DESC, source_id ASC
        scored_sources.sort(
            key=lambda x: (-x.weighted_score, -x.authority_score, x.source_id)
        )

        # Policy evaluation: candidates meeting threshold
        qualifying = [s for s in scored_sources if s.weighted_score >= threshold]

        selected: list[SourceScoreBreakdown] = []
        deprioritized: list[SourceScoreBreakdown] = []
        temporal_coverage: dict[str, bool] = {}
        requirement_coverage: dict[str, str] = {}
        unmet_reqs: list[str] = []

        # If no source qualifies
        if not qualifying:
            for s in scored_sources:
                s.selection_status = SelectionStatus.NO_SUITABLE_SOURCE
                s.score_explanation = (
                    f"No suitable source: weighted score ({s.weighted_score:.3f}) fell below selection "
                    f"threshold ({threshold:.2f})."
                )
                deprioritized.append(s)

            summary = (
                f"NO_SUITABLE_SOURCE: No available knowledge source met the minimum relevance threshold "
                f"of {threshold:.2f} for this query."
            )
            for req in query_analysis.information_requirements:
                requirement_coverage[req] = "unmet"
                unmet_reqs.append(req)

            if query_analysis.temporal_requirement in (TemporalRequirement.COMPARATIVE, TemporalRequirement.MIXED):
                temporal_coverage["current"] = False
                temporal_coverage["historical"] = False
            elif query_analysis.temporal_requirement == TemporalRequirement.CURRENT:
                temporal_coverage["current"] = False
            elif query_analysis.temporal_requirement == TemporalRequirement.HISTORICAL:
                temporal_coverage["historical"] = False
            else:
                temporal_coverage["time_independent"] = False

        else:
            # Multi-requirement & temporal preservation policy
            temporal = query_analysis.temporal_requirement
            needs_historical = temporal in (TemporalRequirement.HISTORICAL, TemporalRequirement.COMPARATIVE, TemporalRequirement.MIXED)
            needs_current = temporal in (TemporalRequirement.CURRENT, TemporalRequirement.COMPARATIVE, TemporalRequirement.MIXED)

            selected_source_ids: set[str] = set()

            def can_select() -> bool:
                return len(selected) < max_sources

            # Helper to check if source provides historical coverage
            def is_hist_source(s_breakdown: SourceScoreBreakdown) -> bool:
                src_prof = next(sp for sp in sources if sp.source_id == s_breakdown.source_id)
                cats = [c.lower() for c in src_prof.available_content_categories + src_prof.supported_query_categories]
                return s_breakdown.source_type == SourceType.CONVERSATION or any("decision" in c or "rationale" in c or "history" in c for c in cats)

            # Helper to check if source provides current baseline coverage
            def is_curr_source(s_breakdown: SourceScoreBreakdown) -> bool:
                src_prof = next(sp for sp in sources if sp.source_id == s_breakdown.source_id)
                cats = [c.lower() for c in src_prof.available_content_categories + src_prof.supported_query_categories]
                return s_breakdown.source_type == SourceType.DOCUMENT or any("configuration" in c or "architecture" in c for c in cats)

            # 1. Comparative / Mixed queries: prioritize preserving both historical and current evidence
            if temporal in (TemporalRequirement.COMPARATIVE, TemporalRequirement.MIXED):
                best_hist = next((s for s in qualifying if is_hist_source(s)), None)
                best_curr = next((s for s in qualifying if is_curr_source(s)), None)

                if best_hist and can_select() and best_hist.source_id not in selected_source_ids:
                    best_hist.selection_status = SelectionStatus.SELECTED
                    selected.append(best_hist)
                    selected_source_ids.add(best_hist.source_id)

                if best_curr and can_select() and best_curr.source_id not in selected_source_ids:
                    best_curr.selection_status = SelectionStatus.SELECTED
                    selected.append(best_curr)
                    selected_source_ids.add(best_curr.source_id)

            # 2. Add top qualifying sources up to max_sources budget
            for s in qualifying:
                if can_select() and s.source_id not in selected_source_ids:
                    s.selection_status = SelectionStatus.SELECTED
                    selected.append(s)
                    selected_source_ids.add(s.source_id)

            # Mark all unselected sources as deprioritized
            for s in scored_sources:
                if s.source_id not in selected_source_ids:
                    s.selection_status = SelectionStatus.DEPRIORITIZED
                    deprioritized.append(s)

            # Re-sort selected in descending score order
            selected.sort(key=lambda x: (-x.weighted_score, -x.authority_score, x.source_id))

            # Generate explanations for each source
            for s in scored_sources:
                src_prof = next(sp for sp in sources if sp.source_id == s.source_id)
                s.score_explanation = generate_source_explanation(
                    query_analysis=query_analysis,
                    source=src_prof,
                    relevance=s.query_relevance_score,
                    authority=s.authority_score,
                    freshness=s.freshness_score,
                    directness=s.directness_score,
                    weighted_score=s.weighted_score,
                    status=s.selection_status,
                    threshold=threshold,
                )

            # Evaluate temporal coverage
            has_cov_hist = any(is_hist_source(s) for s in selected)
            has_cov_curr = any(is_curr_source(s) for s in selected)

            if needs_historical:
                temporal_coverage["historical"] = has_cov_hist
            if needs_current:
                temporal_coverage["current"] = has_cov_curr
            if temporal == TemporalRequirement.TIME_INDEPENDENT:
                temporal_coverage["time_independent"] = len(selected) > 0

            # Evaluate information requirement coverage
            selected_types = {s.source_type for s in selected}
            for req in query_analysis.information_requirements:
                req_lower = req.lower()
                matched_source_id: str | None = None

                if "historical" in req_lower:
                    matched_source = next(
                        (s for s in selected if s.source_type == SourceType.CONVERSATION or is_hist_source(s)),
                        None,
                    )
                    if matched_source:
                        matched_source_id = matched_source.source_id
                elif "configuration" in req_lower or "config" in req_lower:
                    matched_source = next(
                        (s for s in selected if s.source_type == SourceType.DOCUMENT or is_curr_source(s)),
                        None,
                    )
                    if matched_source:
                        matched_source_id = matched_source.source_id
                elif "troubleshoot" in req_lower or "bug" in req_lower:
                    matched_source = next(
                        (s for s in selected if s.source_type == SourceType.TICKET),
                        None,
                    )
                    if matched_source:
                        matched_source_id = matched_source.source_id
                elif "architecture" in req_lower or "technical" in req_lower:
                    matched_source = next(
                        (s for s in selected if s.source_type == SourceType.DOCUMENT),
                        None,
                    )
                    if matched_source:
                        matched_source_id = matched_source.source_id
                elif "general inquiry" in req_lower or "general" in req_lower:
                    if selected:
                        matched_source_id = selected[0].source_id


                if matched_source_id:
                    requirement_coverage[req] = matched_source_id
                else:
                    requirement_coverage[req] = "unmet"
                    unmet_reqs.append(req)

            selected_names = [s.source_name for s in selected]
            if unmet_reqs:
                summary = (
                    f"Selected {len(selected)} source(s) [{', '.join(selected_names)}] exceeding threshold "
                    f"{threshold:.2f} (budget: {max_sources}). Warning: {len(unmet_reqs)} requirement(s) could not be met."
                )
            else:
                summary = (
                    f"Selected {len(selected)} source(s) [{', '.join(selected_names)}] exceeding threshold "
                    f"{threshold:.2f} (budget: {max_sources}). All {len(query_analysis.information_requirements)} information requirements covered."
                )

        duration = time.perf_counter() - start_time
        log.info(
            "Source selection completed in %.3fs: %d selected, %d deprioritized",
            duration,
            len(selected),
            len(deprioritized),
        )

        return SourceSelectionResult(
            query_analysis=query_analysis,
            ranked_sources=scored_sources,
            selected_sources=selected,
            deprioritized_sources=deprioritized,
            selection_threshold=threshold,
            maximum_selected_sources=max_sources,
            temporal_coverage=temporal_coverage,
            information_requirement_coverage=requirement_coverage,
            unmet_information_requirements=unmet_reqs,
            selection_summary=summary,
        )

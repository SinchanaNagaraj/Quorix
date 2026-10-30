"""Deterministic Explanation Generator for Source Selection Decisions."""
from __future__ import annotations

from app.intelligence.query_analysis.schemas import QueryAnalysis, QueryIntent
from app.intelligence.source_selection.schemas import SelectionStatus, SourceProfile
from app.schemas.source import SourceType


def generate_source_explanation(
    query_analysis: QueryAnalysis,
    source: SourceProfile,
    relevance: float,
    authority: float,
    freshness: float,
    directness: float,
    weighted_score: float,
    status: SelectionStatus,
    threshold: float,
) -> str:
    """Generate a precise, deterministic explanation based on factors and query intent."""
    intent = query_analysis.primary_intent
    st = source.source_type

    if status == SelectionStatus.SELECTED:
        if intent in (QueryIntent.HISTORICAL_REASONING, QueryIntent.DECISION_HISTORY):
            if st == SourceType.CONVERSATION:
                return (
                    f"Prioritized (weighted score {weighted_score:.3f} >= {threshold:.2f}) because the query asks "
                    f"about historical reasoning. Engineering discussions offer the highest directness ({directness:.2f}) "
                    f"and relevant team decision context."
                )
            elif st == SourceType.TICKET:
                return (
                    f"Selected (weighted score {weighted_score:.3f} >= {threshold:.2f}) to supply implementation milestones "
                    f"and resolution notes complementing the historical query."
                )
            else:
                return (
                    f"Selected (weighted score {weighted_score:.3f} >= {threshold:.2f}) due to high authority ({authority:.2f}) "
                    f"providing official architectural documentation."
                )

        elif intent == QueryIntent.CONFIGURATION_LOOKUP:
            if st == SourceType.DOCUMENT:
                return (
                    f"Prioritized (weighted score {weighted_score:.3f} >= {threshold:.2f}) as the authoritative source ({authority:.2f}) "
                    f"for current configuration values with maximum expected directness ({directness:.2f})."
                )
            elif st == SourceType.TICKET:
                return (
                    f"Selected (weighted score {weighted_score:.3f} >= {threshold:.2f}) to verify recent deployment and change tickets "
                    f"affecting the active configuration."
                )
            else:
                return (
                    f"Selected (weighted score {weighted_score:.3f} >= {threshold:.2f}) providing auxiliary context on configuration changes."
                )

        elif intent in (QueryIntent.TROUBLESHOOTING, QueryIntent.IMPLEMENTATION_DETAILS):
            if st == SourceType.TICKET:
                return (
                    f"Prioritized (weighted score {weighted_score:.3f} >= {threshold:.2f}) because development tickets contain specific "
                    f"bug reports, stack traces, and verified resolutions."
                )
            else:
                return (
                    f"Selected (weighted score {weighted_score:.3f} >= {threshold:.2f}) to provide supporting debugging discussion and context."
                )

        elif intent == QueryIntent.COMPARISON:
            return (
                f"Selected (weighted score {weighted_score:.3f} >= {threshold:.2f}) for comparative analysis; contributes "
                f"relevance ({relevance:.2f}) and freshness ({freshness:.2f}) across time periods."
            )

        elif query_analysis.requires_multiple_sources:
            return (
                f"Selected (weighted score {weighted_score:.3f} >= {threshold:.2f}) to fulfill distinct information requirements "
                f"identified in the multi-part query."
            )

        else:
            return (
                f"Selected with weighted score {weighted_score:.3f} exceeding threshold {threshold:.2f} "
                f"(relevance: {relevance:.2f}, authority: {authority:.2f}, freshness: {freshness:.2f}, directness: {directness:.2f})."
            )

    else:  # DEPRIORITIZED or NO_SUITABLE_SOURCE
        if weighted_score < threshold:
            return (
                f"Deprioritized because weighted score ({weighted_score:.3f}) fell below the selection threshold "
                f"of {threshold:.2f}. Expected directness ({directness:.2f}) is insufficient for this query intent."
            )
        else:
            return (
                f"Deprioritized despite score ({weighted_score:.3f}) exceeding threshold {threshold:.2f} because higher-ranking "
                f"sources satisfied all query requirements within the maximum selection budget."
            )

"""Expected Directness Scorer (Factor D: 20%).

Estimates the probability that a knowledge source contains an immediate, direct
answer to the user's specific information requirement, rather than merely peripheral
or background context.
Normalized to [0.0, 1.0].
"""
from __future__ import annotations

from app.intelligence.query_analysis.schemas import (
    InformationCategory,
    QueryAnalysis,
    QueryIntent,
)
from app.intelligence.source_selection.schemas import SourceProfile
from app.schemas.source import SourceType


class DirectnessScorer:
    """Calculates expected directness score D for a knowledge source."""

    def score(self, query_analysis: QueryAnalysis, source: SourceProfile) -> float:
        """Calculate normalized directness score in [0.0, 1.0]."""
        intent = query_analysis.primary_intent
        categories = query_analysis.expected_information_categories
        st = source.source_type

        # Base directness mapping by Intent and SourceType
        if intent == QueryIntent.CONFIGURATION_LOOKUP:
            if st == SourceType.DOCUMENT:
                base = 0.95
            elif st == SourceType.TICKET:
                base = 0.75
            else:
                base = 0.40

        elif intent in (QueryIntent.HISTORICAL_REASONING, QueryIntent.DECISION_HISTORY):
            if st == SourceType.CONVERSATION:
                base = 0.95
            elif st == SourceType.TICKET:
                base = 0.80
            else:
                base = 0.55

        elif intent in (QueryIntent.TROUBLESHOOTING, QueryIntent.IMPLEMENTATION_DETAILS):
            if st == SourceType.TICKET:
                base = 0.95
            elif st == SourceType.CONVERSATION:
                base = 0.85
            else:
                base = 0.50

        elif intent == QueryIntent.TECHNICAL_EXPLANATION:
            if st == SourceType.DOCUMENT:
                base = 0.95
            elif st == SourceType.CONVERSATION:
                base = 0.70
            else:
                base = 0.55

        elif intent == QueryIntent.COMPARISON:
            if st in (SourceType.DOCUMENT, SourceType.CONVERSATION, SourceType.TICKET):
                base = 0.85
            else:
                base = 0.60

        elif intent == QueryIntent.GENERAL_INFORMATION:
            base = 0.35

        else:
            base = 0.65

        # Check secondary intent directness bonuses
        for sec in query_analysis.secondary_intents:
            if sec == QueryIntent.CONFIGURATION_LOOKUP and st == SourceType.DOCUMENT:
                base = max(base, 0.90)
            elif sec in (QueryIntent.HISTORICAL_REASONING, QueryIntent.DECISION_HISTORY) and st == SourceType.CONVERSATION:
                base = max(base, 0.90)
            elif sec == QueryIntent.TROUBLESHOOTING and st == SourceType.TICKET:
                base = max(base, 0.90)

        # Content category directness adjustment
        source_cats = [c.lower() for c in source.available_content_categories]
        if InformationCategory.CURRENT_CONFIGURATION in categories and any("configuration" in c for c in source_cats):
            base = min(1.0, base + 0.05)
        if InformationCategory.HISTORICAL_REASONING in categories and any("decision" in c or "rationale" in c for c in source_cats):
            base = min(1.0, base + 0.05)
        if InformationCategory.BUG_RESOLUTION in categories and any("bug" in c or "fix" in c for c in source_cats):
            base = min(1.0, base + 0.05)

        normalized = max(0.0, min(1.0, base))
        return round(normalized, 4)

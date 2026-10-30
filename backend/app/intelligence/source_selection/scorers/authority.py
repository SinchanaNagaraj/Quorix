"""Source Authority Scorer (Factor A: 25%).

Evaluates source trustworthiness based on predefined authority classifications
and explicit source metadata. Purely deterministic; no LLM involved.
Normalized to [0.0, 1.0].
"""
from __future__ import annotations

from app.intelligence.source_selection.config import AUTHORITY_MAPPINGS
from app.intelligence.source_selection.schemas import SourceProfile
from app.schemas.source import SourceType


class AuthorityScorer:
    """Calculates deterministic authority score A for a knowledge source."""

    def __init__(self, mappings: dict[str, float] | None = None) -> None:
        self.mappings = mappings or AUTHORITY_MAPPINGS

    def score(self, source: SourceProfile) -> float:
        """Calculate normalized authority score in [0.0, 1.0]."""
        # 1. Direct match on qualitative classification string
        if source.authority_level in self.mappings:
            score = self.mappings[source.authority_level]
        # 2. Heuristic based on source_type default if unknown string
        elif source.source_type == SourceType.DOCUMENT:
            score = self.mappings.get("OFFICIAL_TECHNICAL_DOCUMENTATION", 0.95)
        elif source.source_type == SourceType.TICKET:
            score = self.mappings.get("RESOLVED_DEVELOPMENT_TICKET", 0.85)
        elif source.source_type == SourceType.CONVERSATION:
            score = self.mappings.get("ENGINEERING_CONVERSATION", 0.70)
        else:
            score = self.mappings.get("UNKNOWN_AUTHORITY", 0.40)

        # 3. Blend with source's explicit numerical base authority score if provided
        if source.authority_score > 0.0:
            score = (score + source.authority_score) / 2.0

        normalized = max(0.0, min(1.0, score))
        return round(normalized, 4)

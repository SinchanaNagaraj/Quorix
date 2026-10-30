"""Pydantic schemas for Source Selection Engine."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from app.intelligence.query_analysis.schemas import QueryAnalysis
from app.schemas.source import SourceType


class SelectionStatus(str, Enum):
    SELECTED = "SELECTED"
    DEPRIORITIZED = "DEPRIORITIZED"
    NO_SUITABLE_SOURCE = "NO_SUITABLE_SOURCE"


class RelevanceBreakdown(BaseModel):
    """Detailed inspectable subscores for query relevance factor R."""

    semantic_score: float = Field(ge=0.0, le=1.0, description="Semantic / text overlap subscore")
    category_score: float = Field(ge=0.0, le=1.0, description="Information category overlap subscore")
    intent_score: float = Field(ge=0.0, le=1.0, description="Query intent affinity subscore")
    entity_score: float = Field(ge=0.0, le=1.0, description="Named entity match coverage subscore")
    potential_source_boost: float = Field(ge=0.0, le=1.0, description="Boost when source matches potential source types")
    total_score: float = Field(ge=0.0, le=1.0, description="Final combined normalized relevance score")


class SourceProfile(BaseModel):
    """Normalized metadata abstraction for a knowledge source."""

    source_id: str = Field(description="Unique source identifier, e.g. SRC-DOCS")
    source_type: SourceType = Field(description="Source type: document, conversation, or ticket")
    source_name: str = Field(description="Human readable name of the source")
    source_description: str = Field(description="Description of scope and contents")
    authority_level: str = Field(description="Qualitative authority classification")
    authority_score: float = Field(ge=0.0, le=1.0, description="Base numerical authority score between 0 and 1")
    last_updated_at: datetime | None = Field(default=None, description="Timestamp of the most recent record")
    created_at: datetime | None = Field(default=None, description="Optional creation timestamp if available")
    available_content_categories: list[str] = Field(
        default_factory=list,
        description="Categories of information contained in this source",
    )
    supported_query_categories: list[str] = Field(
        default_factory=list,
        description="Query topics and types best served by this source",
    )
    retrieval_cost: float | None = Field(
        default=None,
        description="Estimated relative retrieval cost if applicable",
    )
    source_status: str = Field(default="active", description="Operational status: active, available, etc.")


class SourceScoreBreakdown(BaseModel):
    """Detailed score breakdown and decision for an individual knowledge source."""

    source_id: str
    source_type: SourceType
    source_name: str
    query_relevance_score: float = Field(ge=0.0, le=1.0, description="Query relevance factor (0-1)")
    authority_score: float = Field(ge=0.0, le=1.0, description="Source authority factor (0-1)")
    freshness_score: float = Field(ge=0.0, le=1.0, description="Source freshness factor (0-1)")
    directness_score: float = Field(ge=0.0, le=1.0, description="Expected directness factor (0-1)")
    weighted_score: float = Field(ge=0.0, le=1.0, description="Final weighted score: 0.35R + 0.25A + 0.20F + 0.20D")
    selection_status: SelectionStatus = Field(description="Decision: SELECTED, DEPRIORITIZED, or NO_SUITABLE_SOURCE")
    freshness_classification: str = Field(description="Explanation of how freshness was scored based on query temporal intent")
    score_explanation: str = Field(description="Deterministic explanation of selection decision")
    relevance_breakdown: RelevanceBreakdown | None = Field(
        default=None,
        description="Detailed inspectable breakdown of query relevance subscores",
    )


class SourceSelectionResult(BaseModel):
    """Complete source selection result including analysis, rankings, and summary."""

    query_analysis: QueryAnalysis
    ranked_sources: list[SourceScoreBreakdown] = Field(description="All evaluated sources in descending score order")
    selected_sources: list[SourceScoreBreakdown] = Field(description="Sources selected for retrieval")
    deprioritized_sources: list[SourceScoreBreakdown] = Field(description="Sources excluded or deprioritized")
    selection_threshold: float = Field(description="Minimum score threshold required for selection")
    maximum_selected_sources: int = Field(description="Maximum number of sources permitted for selection")
    temporal_coverage: dict[str, bool] = Field(
        default_factory=dict,
        description="Verification of temporal coverage across required periods (e.g. historical, current)",
    )
    information_requirement_coverage: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of each information requirement to the covering source ID or 'unmet'",
    )
    unmet_information_requirements: list[str] = Field(
        default_factory=list,
        description="Query information requirements not covered by selected sources",
    )
    selection_summary: str = Field(description="Executive summary of the selection decision")

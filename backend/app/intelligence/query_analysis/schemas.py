"""Pydantic models and Enums for Query Analysis Engine."""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field

from app.schemas.source import SourceType


class QueryIntent(str, Enum):
    FACTUAL_LOOKUP = "FACTUAL_LOOKUP"
    TECHNICAL_EXPLANATION = "TECHNICAL_EXPLANATION"
    HISTORICAL_REASONING = "HISTORICAL_REASONING"
    CONFIGURATION_LOOKUP = "CONFIGURATION_LOOKUP"
    TROUBLESHOOTING = "TROUBLESHOOTING"
    IMPLEMENTATION_DETAILS = "IMPLEMENTATION_DETAILS"
    COMPARISON = "COMPARISON"
    CHANGE_ANALYSIS = "CHANGE_ANALYSIS"
    DECISION_HISTORY = "DECISION_HISTORY"
    MULTI_PART_QUERY = "MULTI_PART_QUERY"
    GENERAL_INFORMATION = "GENERAL_INFORMATION"


class TemporalRequirement(str, Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    COMPARATIVE = "COMPARATIVE"
    TIME_INDEPENDENT = "TIME_INDEPENDENT"
    MIXED = "MIXED"


class InformationCategory(str, Enum):
    HISTORICAL_REASONING = "HISTORICAL_REASONING"
    CURRENT_CONFIGURATION = "CURRENT_CONFIGURATION"
    TECHNICAL_EXPLANATION = "TECHNICAL_EXPLANATION"
    IMPLEMENTATION_DETAILS = "IMPLEMENTATION_DETAILS"
    TROUBLESHOOTING = "TROUBLESHOOTING"
    DECISION_HISTORY = "DECISION_HISTORY"
    ARCHITECTURE = "ARCHITECTURE"
    BUG_RESOLUTION = "BUG_RESOLUTION"
    GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"


class QueryAnalysis(BaseModel):
    """Structured representation of a user query produced by the Query Analysis Engine."""

    original_query: str = Field(description="Exact original question supplied by the user")
    normalized_query: str = Field(description="Cleaned and normalized query representation")
    primary_intent: QueryIntent = Field(description="Main objective of the query")
    secondary_intents: list[QueryIntent] = Field(
        default_factory=list,
        description="Additional objectives when the query contains multiple requirements",
    )
    entities: list[str] = Field(
        default_factory=list,
        description="Technologies, products, services, components, and named entities",
    )
    technical_keywords: list[str] = Field(
        default_factory=list,
        description="Important terms used to identify relevant knowledge",
    )
    information_requirements: list[str] = Field(
        default_factory=list,
        description="Specific types of information needed to answer the question",
    )
    temporal_requirement: TemporalRequirement = Field(
        description="Temporal characteristic: CURRENT, HISTORICAL, COMPARATIVE, TIME_INDEPENDENT, or MIXED",
    )
    expected_information_categories: list[InformationCategory] = Field(
        default_factory=list,
        description="Categories of information expected to answer the query",
    )
    potential_source_types: list[SourceType] = Field(
        default_factory=list,
        description="Potential knowledge source types (document, conversation, ticket)",
    )
    requires_multiple_sources: bool = Field(
        default=False,
        description="Whether answering the query requires multiple distinct knowledge sources",
    )
    analysis_explanation: str = Field(
        description="Short explanation of what the user is asking and what information is required",
    )
    analysis_method: str = Field(
        default="deterministic",
        description="Method used for query analysis: deterministic or gemini",
    )
    temporal_anchor: str | None = Field(
        default=None,
        description="Extracted date, year, event, or historical milestone if present in query",
    )


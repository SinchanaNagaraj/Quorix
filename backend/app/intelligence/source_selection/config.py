"""Centralized configuration for Source Selection Engine scoring and policies."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, model_validator

from app.core.config import get_settings


class ScoringWeights(BaseModel):
    """Normalized weights for the four source selection scoring factors."""

    relevance: float = Field(default=0.35, ge=0.0, le=1.0)
    authority: float = Field(default=0.25, ge=0.0, le=1.0)
    freshness: float = Field(default=0.20, ge=0.0, le=1.0)
    directness: float = Field(default=0.20, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_sum(self) -> "ScoringWeights":
        total = self.relevance + self.authority + self.freshness + self.directness
        if not math.isclose(total, 1.0, rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")
        return self


# Initial authority level heuristic ratings
AUTHORITY_MAPPINGS: dict[str, float] = {
    "APPROVED_ARCHITECTURE": 1.00,
    "OFFICIAL_TECHNICAL_DOCUMENTATION": 0.95,
    "VERIFIED_ENGINEERING_DECISION": 0.90,
    "MAINTAINED_CONFIGURATION_RECORD": 0.90,
    "RESOLVED_DEVELOPMENT_TICKET": 0.85,
    "ACTIVE_DEVELOPMENT_TICKET": 0.75,
    "ENGINEERING_CONVERSATION": 0.70,
    "INFORMAL_DISCUSSION": 0.55,
    "UNKNOWN_AUTHORITY": 0.40,
}


class SourceSelectionSettings(BaseModel):
    """Complete operational configuration for source selection."""

    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    selection_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    max_selected_sources: int = Field(default=3, ge=1)
    reference_date: datetime | None = Field(
        default=None,
        description="Optional fixed reference date for reproducible testing/eval. If None, uses current UTC time.",
    )
    dataset_as_of: datetime | None = Field(
        default=None,
        description="Alias for reference_date",
    )
    freshness_half_life_days: float = Field(default=180.0, gt=0.0)
    missing_timestamp_score: float = Field(default=0.50, ge=0.0, le=1.0)
    future_timestamp_score: float = Field(default=1.0, ge=0.0, le=1.0)
    neutral_temporal_score: float = Field(default=0.75, ge=0.0, le=1.0)

    @classmethod
    def from_app_settings(cls) -> "SourceSelectionSettings":
        app_settings = get_settings()
        weights = ScoringWeights(
            relevance=app_settings.weight_relevance,
            authority=app_settings.weight_authority,
            freshness=app_settings.weight_freshness,
            directness=app_settings.weight_directness,
        )
        as_of_dt: datetime | None = None
        if app_settings.dataset_as_of:
            try:
                as_of_dt = datetime.fromisoformat(app_settings.dataset_as_of.replace("Z", "+00:00"))
                if as_of_dt.tzinfo is None:
                    as_of_dt = as_of_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                as_of_dt = None

        return cls(
            weights=weights,
            selection_threshold=app_settings.selection_threshold,
            max_selected_sources=app_settings.max_selected_sources,
            reference_date=as_of_dt,
            dataset_as_of=as_of_dt,
            freshness_half_life_days=app_settings.freshness_half_life_days,
        )

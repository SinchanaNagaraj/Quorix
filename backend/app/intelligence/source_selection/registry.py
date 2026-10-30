"""Source Registry and Catalog abstraction.

Provides a unified interface to discover and query metadata for knowledge sources
without retrieving underlying document chunks or connecting to Qdrant.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.intelligence.source_selection.schemas import SourceProfile
from app.schemas.source import SourceType

log = logging.getLogger(__name__)

DEFAULT_SOURCE_PROFILES: list[dict[str, Any]] = [
    {
        "source_id": "SRC-DOCS",
        "source_type": SourceType.DOCUMENT,
        "source_name": "Atlas Technical Documents",
        "source_description": (
            "Approved and draft technical documentation: architecture, caching, security, "
            "API specification, engineering guidelines, configuration reference, deployment "
            "runbook, observability guide, database guide."
        ),
        "authority_level": "OFFICIAL_TECHNICAL_DOCUMENTATION",
        "authority_score": 0.90,
        "last_updated_at": datetime(2025, 2, 18, 9, 45, tzinfo=timezone.utc),
        "available_content_categories": [
            "configuration values",
            "architecture",
            "api contract",
            "security policy",
            "engineering process",
            "runbooks",
            "database schema",
        ],
        "supported_query_categories": [
            "current configuration lookup",
            "how something is designed",
            "policy and process",
            "technical explanation",
            "architecture",
        ],
        "source_status": "active",
    },
    {
        "source_id": "SRC-CONV",
        "source_type": SourceType.CONVERSATION,
        "source_name": "Atlas Engineering Conversations",
        "source_description": (
            "Engineering channel discussions: design proposals, decision debates, incident "
            "post-mortems, debugging threads, team rationale, and casual chatter."
        ),
        "authority_level": "ENGINEERING_CONVERSATION",
        "authority_score": 0.70,
        "last_updated_at": datetime(2025, 3, 5, 10, 18, tzinfo=timezone.utc),
        "available_content_categories": [
            "decision rationale",
            "historical design reasoning",
            "debugging discussion",
            "open questions",
            "incident discussion",
        ],
        "supported_query_categories": [
            "why was X decided",
            "historical context",
            "team reasoning",
            "decision history",
            "historical reasoning",
        ],
        "source_status": "active",
    },
    {
        "source_id": "SRC-TICKETS",
        "source_type": SourceType.TICKET,
        "source_name": "Atlas Development Tickets",
        "source_description": (
            "Bug reports, features, tasks, incidents and improvements with status, "
            "timestamps, implementation details and resolution notes."
        ),
        "authority_level": "RESOLVED_DEVELOPMENT_TICKET",
        "authority_score": 0.80,
        "last_updated_at": datetime(2025, 3, 12, 10, 0, tzinfo=timezone.utc),
        "available_content_categories": [
            "what changed and when",
            "bug history",
            "implementation status",
            "incident records",
            "bug resolution",
            "tasks",
        ],
        "supported_query_categories": [
            "when/what was changed",
            "status of work",
            "bug and fix history",
            "troubleshooting",
            "bug resolution",
        ],
        "source_status": "active",
    },
]


class SourceRegistry:
    """Registry providing abstract SourceProfiles from configuration or local files."""

    def __init__(self, registry_file: Path | None = None) -> None:
        self.registry_file = registry_file or (get_settings().data_dir / "source_registry.json")
        self._sources: dict[str, SourceProfile] = {}
        self._load()

    def _load(self) -> None:
        if self.registry_file and self.registry_file.is_file():
            try:
                raw = json.loads(self.registry_file.read_text(encoding="utf-8"))
                for item in raw.get("sources", []):
                    profile = self._parse_json_entry(item)
                    self._sources[profile.source_id] = profile
                log.info("Loaded %d knowledge sources from %s", len(self._sources), self.registry_file)
                return
            except Exception as exc:
                log.warning("Could not load source registry file %s: %s; falling back to defaults.", self.registry_file, exc)

        # Fallback to defaults
        for raw in DEFAULT_SOURCE_PROFILES:
            profile = SourceProfile.model_validate(raw)
            self._sources[profile.source_id] = profile
        log.info("Loaded %d default knowledge sources", len(self._sources))

    def _parse_json_entry(self, data: dict[str, Any]) -> SourceProfile:
        st_val = data.get("source_type", "document").lower()
        source_type = SourceType(st_val)

        auth_meta = data.get("authority_metadata", {})
        base_auth = float(auth_meta.get("base_authority", 0.75))

        # Map authority level name
        if source_type == SourceType.DOCUMENT:
            auth_level_name = "OFFICIAL_TECHNICAL_DOCUMENTATION" if base_auth >= 0.85 else "APPROVED_ARCHITECTURE"
        elif source_type == SourceType.CONVERSATION:
            auth_level_name = "ENGINEERING_CONVERSATION"
        else:
            auth_level_name = "RESOLVED_DEVELOPMENT_TICKET"

        fresh_meta = data.get("freshness_metadata", {})
        ts_str = fresh_meta.get("last_updated")
        last_updated: datetime | None = None
        if ts_str:
            try:
                last_updated = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=timezone.utc)
            except ValueError:
                last_updated = None

        return SourceProfile(
            source_id=data["source_id"],
            source_type=source_type,
            source_name=data.get("name", data["source_id"]),
            source_description=data.get("description", ""),
            authority_level=auth_level_name,
            authority_score=base_auth,
            last_updated_at=last_updated,
            available_content_categories=data.get("content_categories", []),
            supported_query_categories=data.get("best_for", []),
            retrieval_cost=data.get("retrieval_cost"),
            source_status="active",
        )

    def get_all_sources(self) -> list[SourceProfile]:
        """Return all registered source profiles."""
        return list(self._sources.values())

    def get_source(self, source_id: str) -> SourceProfile | None:
        """Lookup a source profile by identifier."""
        return self._sources.get(source_id)

    def register_source(self, profile: SourceProfile) -> None:
        """Register a new source profile (enables future extensible adapters)."""
        self._sources[profile.source_id] = profile

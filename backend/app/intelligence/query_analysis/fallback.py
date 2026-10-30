"""Deterministic rule-based query analysis fallback.

Performs query analysis without external LLM dependencies, guaranteeing that
the system never becomes unusable when Gemini or network access is unavailable.
Uses configurable DomainVocabulary for domain terms, entity aliases, and intent signals.
"""
from __future__ import annotations

import re
from typing import Sequence

from app.core.text import normalize_text
from app.intelligence.query_analysis.schemas import (
    InformationCategory,
    QueryAnalysis,
    QueryIntent,
    TemporalRequirement,
)
from app.intelligence.query_analysis.vocabulary import DomainVocabulary, get_default_vocabulary
from app.schemas.source import SourceType


def extract_entities(query: str, vocabulary: DomainVocabulary | None = None) -> list[str]:
    """Extract recognized technical entities and normalize aliases."""
    vocab = vocabulary or get_default_vocabulary()
    found: list[str] = []
    seen_canonical: set[str] = set()
    lower_query = query.lower()

    # 1. Match known entities
    for entity in vocab.known_entities:
        pattern = r"\b" + re.escape(entity.lower()) + r"\b"
        if re.search(pattern, lower_query):
            canonical = vocab.entity_aliases.get(entity.lower(), entity)
            if canonical.lower() not in seen_canonical:
                seen_canonical.add(canonical.lower())
                found.append(canonical)

    # 2. Match aliases
    for alias, canonical in vocab.entity_aliases.items():
        pattern = r"\b" + re.escape(alias.lower()) + r"\b"
        if re.search(pattern, lower_query):
            if canonical.lower() not in seen_canonical:
                seen_canonical.add(canonical.lower())
                found.append(canonical)

    return found


def extract_technical_keywords(
    query: str, entities: Sequence[str], vocabulary: DomainVocabulary | None = None
) -> list[str]:
    """Extract informative non-stopword tokens as technical keywords."""
    vocab = vocabulary or get_default_vocabulary()
    tokens = re.findall(r"\b[A-Za-z0-9_-]+\b", query)
    keywords: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        low = tok.lower()
        if low not in vocab.stop_words and len(low) > 1 and low not in seen:
            seen.add(low)
            keywords.append(tok)
    return keywords


def extract_temporal_anchor(query: str) -> str | None:
    """Extract explicit date, year, month, or historical event mention if present."""
    lower_q = query.lower()
    # Check for specific year e.g. 2024, 2025
    year_match = re.search(r"\b(20[2-3][0-9])\b", lower_q)
    if year_match:
        # Check if preceded by month
        month_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+"
            + year_match.group(1),
            lower_q,
        )
        if month_match:
            return month_match.group(0).title()
        return year_match.group(1)

    # Check for event anchors
    for anchor in ("august outage", "outage", "initial release", "v1", "v2", "migration", "original design"):
        if anchor in lower_q:
            return anchor.title()

    return None


def analyze_query_deterministically(
    raw_query: str, vocabulary: DomainVocabulary | None = None
) -> QueryAnalysis:
    """Analyze query using deterministic rule-based heuristics and domain vocabulary."""
    vocab = vocabulary or get_default_vocabulary()
    normalized = normalize_text(raw_query).strip()
    lower_q = normalized.lower()

    entities = extract_entities(normalized, vocab)
    keywords = extract_technical_keywords(normalized, entities, vocab)
    temporal_anchor = extract_temporal_anchor(normalized)

    # 1. Check for domain relevance / General Information
    is_domain_relevant = bool(entities) or any(
        kw.lower() in {
            "config", "configuration", "timeout", "error", "architecture", "incident",
            "bug", "latency", "deploy", "service", "gateway", "database", "cache", "token",
        }
        for kw in keywords
    )

    if not is_domain_relevant and ("not present" in lower_q or "tell me something" in lower_q or len(keywords) == 0):
        return QueryAnalysis(
            original_query=raw_query,
            normalized_query=normalized,
            primary_intent=QueryIntent.GENERAL_INFORMATION,
            secondary_intents=[],
            entities=[],
            technical_keywords=keywords,
            information_requirements=["General inquiry not directly mapped to system records"],
            temporal_requirement=TemporalRequirement.TIME_INDEPENDENT,
            expected_information_categories=[InformationCategory.GENERAL_KNOWLEDGE],
            potential_source_types=[SourceType.DOCUMENT],
            requires_multiple_sources=False,
            analysis_explanation="Query does not refer to known system components; treated as general knowledge inquiry.",
            analysis_method="deterministic",
            temporal_anchor=temporal_anchor,
        )

    # 2. Check multi-part query patterns
    has_multi_part = (
        bool(re.search(r",\s*and\s+(?:what|how|why|which)\b", lower_q))
        or bool(re.search(r"\band\s+what\s+is\b", lower_q))
        or bool(re.search(r"\band\s+how\s+(?:was|is)\b", lower_q))
        or ("," in lower_q and ("what is" in lower_q or "how" in lower_q) and ("why" in lower_q or "which" in lower_q))
    )

    # 3. Temporal Requirement Identification
    has_current = bool(re.search(r"\b(current|currently|now|latest|active|present|today|new)\b", lower_q))
    has_historical = bool(
        re.search(r"\b(why was|why did|originally|initial|historical|previously|deprecated|past|earlier|before|prior|old)\b", lower_q)
        or (temporal_anchor is not None and not has_current)
    )
    has_comparative = bool(
        re.search(r"\b(compare|difference|change(?:d)? over time|old and new|previous and current|vs|versus|how has .* changed)\b", lower_q)
    )

    if has_comparative or ("old" in lower_q and "new" in lower_q) or ("previous" in lower_q and "current" in lower_q):
        temporal = TemporalRequirement.COMPARATIVE
    elif has_current and has_historical:
        temporal = TemporalRequirement.MIXED
    elif has_current:
        temporal = TemporalRequirement.CURRENT
    elif has_historical:
        temporal = TemporalRequirement.HISTORICAL
    else:
        temporal = TemporalRequirement.TIME_INDEPENDENT

    # 4. Intent Classification
    primary_intent: QueryIntent
    secondary_intents: list[QueryIntent] = []
    expected_categories: list[InformationCategory] = []
    potential_sources: list[SourceType] = []

    # Detect specific intents using domain vocabulary
    is_why = (
        lower_q.startswith("why")
        or any(w in lower_q for w in vocab.intent_keywords["historical"])
    )
    is_config = any(w in lower_q for w in vocab.intent_keywords["config"])
    is_troubleshoot = any(w in lower_q for w in vocab.intent_keywords["troubleshoot"])
    is_arch = any(w in lower_q for w in vocab.intent_keywords["architecture"])

    if has_multi_part:
        if is_why and is_config:
            primary_intent = QueryIntent.HISTORICAL_REASONING
            secondary_intents = [QueryIntent.CONFIGURATION_LOOKUP]
            expected_categories = [
                InformationCategory.HISTORICAL_REASONING,
                InformationCategory.CURRENT_CONFIGURATION,
            ]
            potential_sources = [SourceType.CONVERSATION, SourceType.DOCUMENT, SourceType.TICKET]
        elif is_troubleshoot:
            primary_intent = QueryIntent.TROUBLESHOOTING
            secondary_intents = [QueryIntent.IMPLEMENTATION_DETAILS]
            expected_categories = [
                InformationCategory.TROUBLESHOOTING,
                InformationCategory.BUG_RESOLUTION,
            ]
            potential_sources = [SourceType.TICKET, SourceType.CONVERSATION]
        else:
            primary_intent = QueryIntent.MULTI_PART_QUERY
            expected_categories = [InformationCategory.TECHNICAL_EXPLANATION]
            potential_sources = [SourceType.DOCUMENT, SourceType.CONVERSATION]
    elif temporal == TemporalRequirement.COMPARATIVE or has_comparative:
        primary_intent = QueryIntent.COMPARISON
        secondary_intents = [QueryIntent.CHANGE_ANALYSIS]
        expected_categories = [
            InformationCategory.HISTORICAL_REASONING,
            InformationCategory.CURRENT_CONFIGURATION,
        ]
        potential_sources = [SourceType.DOCUMENT, SourceType.TICKET, SourceType.CONVERSATION]
    elif is_why:
        primary_intent = QueryIntent.HISTORICAL_REASONING
        secondary_intents = [QueryIntent.DECISION_HISTORY]
        expected_categories = [
            InformationCategory.HISTORICAL_REASONING,
            InformationCategory.DECISION_HISTORY,
        ]
        potential_sources = [SourceType.CONVERSATION, SourceType.DOCUMENT, SourceType.TICKET]
    elif is_config:
        primary_intent = QueryIntent.CONFIGURATION_LOOKUP
        secondary_intents = [QueryIntent.FACTUAL_LOOKUP]
        expected_categories = [InformationCategory.CURRENT_CONFIGURATION]
        potential_sources = [SourceType.DOCUMENT, SourceType.TICKET]
    elif is_troubleshoot:
        primary_intent = QueryIntent.TROUBLESHOOTING
        secondary_intents = [QueryIntent.IMPLEMENTATION_DETAILS]
        expected_categories = [
            InformationCategory.TROUBLESHOOTING,
            InformationCategory.BUG_RESOLUTION,
        ]
        potential_sources = [SourceType.TICKET, SourceType.CONVERSATION]
    elif is_arch:
        primary_intent = QueryIntent.TECHNICAL_EXPLANATION
        expected_categories = [
            InformationCategory.ARCHITECTURE,
            InformationCategory.TECHNICAL_EXPLANATION,
        ]
        potential_sources = [SourceType.DOCUMENT]
    else:
        primary_intent = QueryIntent.FACTUAL_LOOKUP
        expected_categories = [InformationCategory.TECHNICAL_EXPLANATION]
        potential_sources = [SourceType.DOCUMENT]

    # Ensure unique preserving order
    unique_sources: list[SourceType] = []
    for s in potential_sources:
        if s not in unique_sources:
            unique_sources.append(s)

    requires_multiple = (
        has_multi_part
        or temporal in (TemporalRequirement.MIXED, TemporalRequirement.COMPARATIVE)
        or len(expected_categories) > 1
        or primary_intent == QueryIntent.COMPARISON
    )

    info_reqs: list[str] = []
    for cat in expected_categories:
        info_reqs.append(
            f"Information on {cat.value.lower().replace('_', ' ')} for {', '.join(entities) if entities else 'query topic'}"
        )

    explanation = (
        f"Query evaluated as {primary_intent.value} with temporal requirement {temporal.value}. "
        f"Key entities: {entities if entities else 'none identified'}. Expected information: "
        f"{[c.value for c in expected_categories]}."
    )

    return QueryAnalysis(
        original_query=raw_query,
        normalized_query=normalized,
        primary_intent=primary_intent,
        secondary_intents=secondary_intents,
        entities=entities,
        technical_keywords=keywords,
        information_requirements=info_reqs,
        temporal_requirement=temporal,
        expected_information_categories=expected_categories,
        potential_source_types=unique_sources,
        requires_multiple_sources=requires_multiple,
        analysis_explanation=explanation,
        analysis_method="deterministic",
        temporal_anchor=temporal_anchor,
    )

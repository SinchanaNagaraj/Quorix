"""Query Relevance Scorer (Factor R: 35%).

Determines how closely a source's description, content categories, and
supported query types relate to the structured query analysis.
Evaluates four normalized sub-dimensions:
1. Semantic / text similarity (with synonym awareness and deterministic token overlap)
2. Category overlap between expected categories and source content categories
3. Intent alignment matching natural affinities between source types and query intents
4. Entity matching evaluating coverage of query entities in source metadata

All subscores are inspectable, normalized to [0.0, 1.0], and operate purely on metadata.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any
from app.intelligence.query_analysis.schemas import QueryAnalysis, QueryIntent
from app.intelligence.query_analysis.vocabulary import DomainVocabulary, get_default_vocabulary
from app.intelligence.source_selection.schemas import RelevanceBreakdown, SourceProfile
from app.schemas.source import SourceType

log = logging.getLogger(__name__)


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class RelevanceScorer:
    """Calculates query relevance score R and inspectable breakdown for a knowledge source."""

    def __init__(
        self,
        embedder: Any | None = None,
        vocabulary: DomainVocabulary | None = None,
    ) -> None:
        self.embedder = embedder
        self.vocabulary = vocabulary or get_default_vocabulary()
        self._source_profile_embeddings: dict[str, list[float]] = {}

    def score(self, query_analysis: QueryAnalysis, source: SourceProfile) -> float:
        """Calculate normalized relevance score in [0.0, 1.0]."""
        return self.score_with_breakdown(query_analysis, source).total_score

    def score_with_breakdown(
        self, query_analysis: QueryAnalysis, source: SourceProfile
    ) -> RelevanceBreakdown:
        """Compute inspectable relevance breakdown with normalized subscores."""
        # 1. Semantic / text similarity between query and source profile (with synonym awareness)
        semantic_score = self._compute_semantic_similarity(query_analysis, source)

        # 2. Information category overlap
        category_score = self._compute_category_overlap(query_analysis, source)

        # 3. Intent alignment bonus / penalty
        intent_score = self._compute_intent_alignment(query_analysis, source)

        # 4. Entity keyword matching with source profile
        entity_score = self._compute_entity_match(query_analysis, source)

        # Weighted combination of relevance components
        raw_score = (
            0.40 * semantic_score
            + 0.30 * category_score
            + 0.20 * intent_score
            + 0.10 * entity_score
        )

        boost = 0.0
        # Boost if query analysis specifically flagged this source type
        if source.source_type in query_analysis.potential_source_types:
            boost = 0.10
            raw_score = min(1.0, raw_score + boost)

        # If general information not in domain dataset, clamp relevance to low baseline
        if query_analysis.primary_intent == QueryIntent.GENERAL_INFORMATION:
            raw_score = min(0.35, raw_score * 0.5)

        total_normalized = max(0.0, min(1.0, round(raw_score, 4)))

        return RelevanceBreakdown(
            semantic_score=round(semantic_score, 4),
            category_score=round(category_score, 4),
            intent_score=round(intent_score, 4),
            entity_score=round(entity_score, 4),
            potential_source_boost=round(boost, 4),
            total_score=total_normalized,
        )

    def _compute_semantic_similarity(
        self, query_analysis: QueryAnalysis, source: SourceProfile
    ) -> float:
        """Cosine similarity via embedding model or deterministic synonym-aware concept overlap."""
        if self.embedder is not None:
            try:
                # Cache source profile embedding
                if source.source_id not in self._source_profile_embeddings:
                    source_text = f"{source.source_name}. {source.source_description} " + " ".join(
                        (source.available_content_categories or []) + (source.supported_query_categories or [])
                    )
                    [emb] = self.embedder.embed_documents([source_text])
                    self._source_profile_embeddings[source.source_id] = emb

                [query_emb] = self.embedder.embed_documents([query_analysis.normalized_query])
                sim = _cosine_similarity(query_emb, self._source_profile_embeddings[source.source_id])
                # Scale from [-1, 1] to [0, 1]
                return max(0.0, min(1.0, (sim + 1.0) / 2.0))
            except Exception as exc:
                log.warning("Embedding similarity failed (%s); using token overlap fallback.", exc)

        # Deterministic concept & synonym overlap
        query_words = set(re.findall(r"\b[a-z0-9_-]+\b", query_analysis.normalized_query.lower()))
        query_words = {w for w in query_words if w not in self.vocabulary.stop_words and len(w) > 1}

        if not query_words:
            return 0.50

        source_text = (
            (source.source_name or "")
            + " "
            + (source.source_description or "")
            + " "
            + " ".join(source.available_content_categories or [])
            + " "
            + " ".join(source.supported_query_categories or [])
        ).lower()
        source_words = set(re.findall(r"\b[a-z0-9_-]+\b", source_text))

        # Check for each query word if it or any of its synonyms matches the source words
        matched_concepts = 0
        for w in query_words:
            if w in source_words:
                matched_concepts += 1
            else:
                # Check synonym families
                matched_syn = False
                for syn_group, syn_list in self.vocabulary.technical_synonyms.items():
                    if w == syn_group or w in syn_list:
                        if syn_group in source_words or any(s in source_words for s in syn_list):
                            matched_syn = True
                            break
                if matched_syn:
                    matched_concepts += 1

        concept_ratio = matched_concepts / max(1, len(query_words))
        return max(0.0, min(1.0, concept_ratio))

    def _compute_category_overlap(
        self, query_analysis: QueryAnalysis, source: SourceProfile
    ) -> float:
        """Match expected information categories with source content categories."""
        if not query_analysis.expected_information_categories:
            return 0.50

        all_source_cats = (source.available_content_categories or []) + (source.supported_query_categories or [])
        if not all_source_cats:
            return 0.0

        source_cats_lower = [c.lower() for c in all_source_cats]
        hits = 0
        total = len(query_analysis.expected_information_categories)
        # Filter out temporal and generic words that don't indicate topical content
        ignored_tokens = {"current", "historical", "general", "details", "expected", "information"}

        for expected in query_analysis.expected_information_categories:
            tokens = [t for t in expected.value.lower().split("_") if t not in ignored_tokens and len(t) > 2]
            if not tokens:
                tokens = expected.value.lower().split("_")
            # If any substantive token matches source categories
            if any(any(tok in sc for sc in source_cats_lower) for tok in tokens):
                hits += 1

        return max(0.0, min(1.0, hits / max(1, total)))


    def _compute_intent_alignment(
        self, query_analysis: QueryAnalysis, source: SourceProfile
    ) -> float:
        """Evaluate how natural the source type is for the primary/secondary intent."""
        intent = query_analysis.primary_intent
        st = source.source_type

        if intent in (QueryIntent.HISTORICAL_REASONING, QueryIntent.DECISION_HISTORY):
            if st == SourceType.CONVERSATION:
                return 0.95
            elif st == SourceType.TICKET:
                return 0.75
            elif st == SourceType.DOCUMENT:
                return 0.65
        elif intent in (QueryIntent.CONFIGURATION_LOOKUP, QueryIntent.FACTUAL_LOOKUP):
            if st == SourceType.DOCUMENT:
                return 0.95
            elif st == SourceType.TICKET:
                return 0.70
            elif st == SourceType.CONVERSATION:
                return 0.40
        elif intent in (QueryIntent.TROUBLESHOOTING, QueryIntent.CHANGE_ANALYSIS):
            if st == SourceType.TICKET:
                return 0.95
            elif st == SourceType.CONVERSATION:
                return 0.80
            elif st == SourceType.DOCUMENT:
                return 0.50
        elif intent == QueryIntent.TECHNICAL_EXPLANATION:
            if st == SourceType.DOCUMENT:
                return 0.95
            elif st == SourceType.CONVERSATION:
                return 0.70
            elif st == SourceType.TICKET:
                return 0.55
        elif intent == QueryIntent.COMPARISON:
            return 0.85  # All sources can potentially contribute to comparison

        return 0.60

    def _compute_entity_match(
        self, query_analysis: QueryAnalysis, source: SourceProfile
    ) -> float:
        """Score based on coverage of query entities in source description and metadata."""
        if not query_analysis.entities:
            return 0.50

        desc_lower = (
            (source.source_name or "")
            + " "
            + (source.source_description or "")
            + " "
            + " ".join(source.available_content_categories or [])
        ).lower()

        matched = 0
        for entity in query_analysis.entities:
            ent_lower = entity.lower()
            if ent_lower in desc_lower:
                matched += 1
            else:
                # Check entity aliases
                alias = self.vocabulary.entity_aliases.get(ent_lower)
                if alias and alias.lower() in desc_lower:
                    matched += 1

        coverage = matched / max(1, len(query_analysis.entities))
        # Scaled smoothly in [0.0, 1.0] without letting a single entity dominate
        return max(0.0, min(1.0, coverage))

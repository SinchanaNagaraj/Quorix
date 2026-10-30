"""Query Analysis Engine.

Accepts natural language questions, extracts intent, temporal requirements,
entities, keywords, and information requirements into a validated QueryAnalysis model.
Supports structured LLM analysis via Google GenAI with deterministic fallback.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.core.config import get_settings
from app.intelligence.query_analysis.fallback import analyze_query_deterministically
from app.intelligence.query_analysis.schemas import QueryAnalysis
from app.intelligence.query_analysis.vocabulary import DomainVocabulary

log = logging.getLogger(__name__)


class QueryAnalyzer:
    """Orchestrates query analysis with Gemini LLM and deterministic fallback."""

    def __init__(
        self,
        gemini_api_key: str | None = None,
        model_name: str | None = None,
        vocabulary: DomainVocabulary | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = gemini_api_key or (
            settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        )
        self.model_name = model_name or settings.gemini_model
        self.vocabulary = vocabulary
        self._client: Any = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as exc:
                log.warning("Could not initialize Google GenAI client: %s", exc)
                self._client = None

    def analyze(self, query: str) -> QueryAnalysis:
        """Analyze a user query, returning a structured QueryAnalysis."""
        start_time = time.perf_counter()
        log.info("Query analysis started for: %r", query)

        # If LLM client is available, attempt structured LLM understanding
        if self._client:
            try:
                analysis = self._analyze_with_gemini(query)
                duration = time.perf_counter() - start_time
                log.info(
                    "Query analysis completed via Gemini in %.3fs: intent=%s, temporal=%s",
                    duration,
                    analysis.primary_intent.value,
                    analysis.temporal_requirement.value,
                )
                return analysis
            except Exception as exc:
                log.warning("Gemini analysis failed (%s); using deterministic fallback.", exc)

        # Deterministic fallback
        analysis = analyze_query_deterministically(query, vocabulary=self.vocabulary)
        duration = time.perf_counter() - start_time
        log.info(
            "Query analysis completed via deterministic engine in %.3fs: intent=%s, temporal=%s",
            duration,
            analysis.primary_intent.value,
            analysis.temporal_requirement.value,
        )
        return analysis

    def _analyze_with_gemini(self, query: str) -> QueryAnalysis:
        from google.genai import types

        prompt = (
            f"Analyze this software engineering knowledge query: {query!r}\n"
            "Identify the primary and secondary intent, named entities, technical keywords, "
            "temporal requirement (CURRENT, HISTORICAL, COMPARATIVE, TIME_INDEPENDENT, MIXED), "
            "expected information categories, and potential source types (document, conversation, ticket)."
        )

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=QueryAnalysis,
                temperature=0.0,
            ),
        )

        text = response.text
        if not text:
            raise ValueError("Empty response from Gemini")
        data = json.loads(text)
        analysis = QueryAnalysis.model_validate(data)
        # Ensure analysis_method is recorded as gemini
        analysis.analysis_method = "gemini"
        return analysis

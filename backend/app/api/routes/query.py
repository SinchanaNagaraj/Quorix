"""API routes for Query Analysis and Intelligent Source Selection."""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.intelligence.query_analysis.analyzer import QueryAnalyzer
from app.intelligence.query_analysis.schemas import QueryAnalysis
from app.intelligence.source_selection.schemas import SourceSelectionResult
from app.intelligence.source_selection.selector import SourceSelector

log = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])

# Singletons for query analyzer and source selector
_analyzer = QueryAnalyzer()
_selector = SourceSelector()


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, description="Natural language user question")


class QueryAnalysisResponse(BaseModel):
    query_analysis: QueryAnalysis


class SourceSelectionResponse(BaseModel):
    query_analysis: QueryAnalysis
    selection: SourceSelectionResult


@router.post("/analyze", response_model=QueryAnalysisResponse, status_code=status.HTTP_200_OK)
def analyze_query(req: QueryRequest) -> QueryAnalysisResponse:
    """Analyze a natural-language query and return its structured query characteristics."""
    try:
        analysis = _analyzer.analyze(req.query)
        return QueryAnalysisResponse(query_analysis=analysis)
    except Exception as exc:
        log.error("Failed to analyze query %r: %s", req.query, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while analyzing the query.",
        ) from exc


@router.post("/select-sources", response_model=SourceSelectionResponse, status_code=status.HTTP_200_OK)
def select_sources(req: QueryRequest) -> SourceSelectionResponse:
    """Analyze query and select the most relevant knowledge sources before retrieval."""
    try:
        analysis = _analyzer.analyze(req.query)
        result = _selector.select_sources(analysis)
        return SourceSelectionResponse(query_analysis=analysis, selection=result)
    except Exception as exc:
        log.error("Failed to select sources for query %r: %s", req.query, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while selecting knowledge sources.",
        ) from exc

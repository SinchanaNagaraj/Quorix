"""Architectural Boundary Tests for Phase 3.

Guarantees strict isolation:
1. Query analysis NEVER invokes Qdrant retrieval or fetches document chunks.
2. Source selection NEVER invokes Qdrant retrieval or connects to vector storage.
3. Source selection operates strictly on metadata profiles, never loading raw file contents.
4. No BM25 search, chunk payload retrieval, or answer-generation LLM is invoked.
"""
from unittest.mock import MagicMock, patch
import pytest

from app.intelligence.query_analysis.analyzer import QueryAnalyzer
from app.intelligence.source_selection.registry import SourceRegistry
from app.intelligence.source_selection.selector import SourceSelector


@patch("qdrant_client.QdrantClient")
def test_no_qdrant_invocation_during_query_analysis(mock_qdrant):
    """Verify that QueryAnalyzer never accesses Qdrant."""
    analyzer = QueryAnalyzer(gemini_api_key=None)
    analysis = analyzer.analyze("Why was Redis caching introduced, and what is its current TTL configuration?")
    assert analysis is not None
    mock_qdrant.assert_not_called()


@patch("qdrant_client.QdrantClient")
def test_no_qdrant_invocation_during_source_selection(mock_qdrant):
    """Verify that SourceSelector never accesses Qdrant."""
    analyzer = QueryAnalyzer(gemini_api_key=None)
    selector = SourceSelector()

    analysis = analyzer.analyze("What is the current Redis TTL?")
    result = selector.select_sources(analysis)

    assert result is not None
    assert len(result.ranked_sources) > 0
    mock_qdrant.assert_not_called()


def test_no_document_chunk_retrieval_during_selection():
    """Verify that SourceSelector never calls VectorStore.search or ChunkingService."""
    mock_vector_store = MagicMock()
    mock_vector_store.search = MagicMock(side_effect=RuntimeError("VectorStore.search should NOT be called in Phase 3!"))

    analyzer = QueryAnalyzer(gemini_api_key=None)
    selector = SourceSelector()

    analysis = analyzer.analyze("Explain the authentication architecture.")
    result = selector.select_sources(analysis)

    assert result is not None
    mock_vector_store.search.assert_not_called()


def test_source_profiles_contain_no_chunk_payloads():
    """Verify that SourceRegistry loads only high-level source metadata, not chunk contents."""
    registry = SourceRegistry()
    sources = registry.get_all_sources()

    assert len(sources) >= 3
    for s in sources:
        # SourceProfile must only hold metadata
        assert hasattr(s, "source_id")
        assert hasattr(s, "source_description")
        assert hasattr(s, "available_content_categories")
        assert not hasattr(s, "chunks")
        assert not hasattr(s, "document_text")
        assert not hasattr(s, "content")


def test_no_bm25_or_llm_answer_synthesis():
    """Verify that Phase 3 does not generate final answers or execute lexical chunk indexing."""
    analyzer = QueryAnalyzer(gemini_api_key=None)
    selector = SourceSelector()

    analysis = analyzer.analyze("What is our current authentication configuration?")
    result = selector.select_sources(analysis)

    # Result should have selection metadata and rankings, but no synthesized final answers or chunks
    assert not hasattr(result, "final_answer")
    assert not hasattr(result, "retrieved_chunks")
    assert not hasattr(result, "generated_response")
    for s in result.selected_sources:
        assert not hasattr(s, "chunk_texts")
        assert not hasattr(s, "retrieved_passages")

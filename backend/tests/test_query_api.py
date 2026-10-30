"""Integration tests for Query Analysis & Source Selection API endpoints."""
from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


def test_api_analyze_endpoint():
    """Test POST /api/v1/query/analyze."""
    payload = {"query": "Why was Redis caching introduced, and what is its current TTL configuration?"}
    response = client.post("/api/v1/query/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "query_analysis" in data
    qa = data["query_analysis"]
    assert qa["original_query"] == payload["query"]
    assert qa["temporal_requirement"] in ("MIXED", "HISTORICAL", "CURRENT")
    assert "Redis" in qa["entities"]
    assert qa["requires_multiple_sources"] is True


def test_api_select_sources_endpoint():
    """Test POST /api/v1/query/select-sources."""
    payload = {"query": "What is the current Redis TTL?"}
    response = client.post("/api/v1/query/select-sources", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "query_analysis" in data
    assert "selection" in data

    selection = data["selection"]
    assert len(selection["ranked_sources"]) >= 3
    assert len(selection["selected_sources"]) >= 1
    assert selection["selection_threshold"] == 0.55
    assert selection["maximum_selected_sources"] == 3

    top = selection["selected_sources"][0]
    assert "source_id" in top
    assert "weighted_score" in top
    assert "score_explanation" in top
    assert top["query_relevance_score"] >= 0.0
    assert top["authority_score"] >= 0.0
    assert top["freshness_score"] >= 0.0
    assert top["directness_score"] >= 0.0


def test_api_select_sources_comparative_flow():
    """Test full flow for comparative query across endpoints."""
    payload = {"query": "How has the Redis configuration changed over time?"}
    response = client.post("/api/v1/query/select-sources", json=payload)
    assert response.status_code == 200
    data = response.json()
    selection = data["selection"]
    assert len(selection["selected_sources"]) >= 2
    types = [s["source_type"] for s in selection["selected_sources"]]
    assert "document" in types


def test_api_validation_error_on_empty_query():
    """Verify request validation rejects empty queries with HTTP 422."""
    response = client.post("/api/v1/query/analyze", json={"query": ""})
    assert response.status_code == 422

    response = client.post("/api/v1/query/select-sources", json={"query": ""})
    assert response.status_code == 422

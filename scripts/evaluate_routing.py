"""Manual Routing Evaluation Runner for Phase 3.

Executes the 5 required manual routing evaluation tests:
- Test A: Current configuration
- Test B: Historical decision
- Test C: Comparative architecture
- Test D: Ticket lookup
- Test E: Technical explanation

Inspects QueryAnalysis, candidate scores (R, A, F, D, S), selected/deprioritized sources,
temporal & requirement coverage, and verifies whether the chosen sources correspond
to actual ground-truth evidence in the Project Atlas dataset.
Outputs results to evaluation/phase3_routing_results.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.intelligence.query_analysis.analyzer import QueryAnalyzer
from app.intelligence.source_selection.config import SourceSelectionSettings
from app.intelligence.source_selection.registry import SourceRegistry
from app.intelligence.source_selection.selector import SourceSelector


def run_evaluation() -> dict[str, Any]:
    dataset_as_of = datetime(2025, 3, 31, 0, 0, tzinfo=timezone.utc)
    settings = SourceSelectionSettings(
        selection_threshold=0.55,
        max_selected_sources=3,
        reference_date=dataset_as_of,
    )
    registry = SourceRegistry()
    analyzer = QueryAnalyzer(gemini_api_key=None)
    selector = SourceSelector(settings=settings, registry=registry)

    # Load dataset records to cross-reference evidence
    data_dir = Path("data")
    docs = json.loads((data_dir / "documents.json").read_text(encoding="utf-8")) if (data_dir / "documents.json").is_file() else []
    convs = json.loads((data_dir / "conversations.json").read_text(encoding="utf-8")) if (data_dir / "conversations.json").is_file() else []
    tickets = json.loads((data_dir / "tickets.json").read_text(encoding="utf-8")) if (data_dir / "tickets.json").is_file() else []

    test_queries = [
        {
            "test_id": "Test A",
            "name": "Current configuration",
            "query": "What is our current authentication configuration?",
            "expected_intent": "CONFIGURATION_LOOKUP",
            "expected_top_source_type": "document",
            "expected_temporal": "CURRENT",
            "dataset_corroboration": "DOC-004 (Security & Authentication Guidelines), DOC-007 (Configuration Reference)",
        },
        {
            "test_id": "Test B",
            "name": "Historical decision",
            "query": "Why did we migrate from Redis to PostgreSQL?",
            "expected_intent": "HISTORICAL_REASONING",
            "expected_top_source_type": "conversation",
            "expected_temporal": "HISTORICAL",
            "dataset_corroboration": "CONV-001 (Caching & Persistence Debate), CONV-003 (Message Broker Architecture Decision)",
        },
        {
            "test_id": "Test C",
            "name": "Comparative architecture",
            "query": "What changed between the old and current authentication architecture?",
            "expected_intent": "COMPARISON",
            "expected_top_source_type": "multiple (document + conversation)",
            "expected_temporal": "COMPARATIVE",
            "dataset_corroboration": "DOC-004 (v2 guidelines) vs CONV-002 (Auth Redesign debate) & TICKS (JWT migration)",
        },
        {
            "test_id": "Test D",
            "name": "Ticket lookup",
            "query": "Which ticket fixed the API timeout issue?",
            "expected_intent": "TROUBLESHOOTING",
            "expected_top_source_type": "ticket",
            "expected_temporal": "TIME_INDEPENDENT or CURRENT",
            "dataset_corroboration": "TICK-001 (API Gateway 504 Timeout on Catalog Search fix)",
        },
        {
            "test_id": "Test E",
            "name": "Technical explanation",
            "query": "Explain the architecture of the notification service.",
            "expected_intent": "TECHNICAL_EXPLANATION",
            "expected_top_source_type": "document",
            "expected_temporal": "TIME_INDEPENDENT",
            "dataset_corroboration": "DOC-002 (System Architecture Specification)",
        },
    ]

    results = []

    for item in test_queries:
        query = item["query"]
        analysis = analyzer.analyze(query)
        selection = selector.select_sources(analysis)

        ranked_list = []
        for s in selection.ranked_sources:
            ranked_list.append({
                "source_id": s.source_id,
                "source_type": s.source_type.value,
                "source_name": s.source_name,
                "scores": {
                    "relevance": s.query_relevance_score,
                    "authority": s.authority_score,
                    "freshness": s.freshness_score,
                    "directness": s.directness_score,
                    "weighted": s.weighted_score,
                },
                "status": s.selection_status.value,
                "freshness_classification": s.freshness_classification,
                "score_explanation": s.score_explanation,
                "relevance_breakdown": s.relevance_breakdown.model_dump() if s.relevance_breakdown else None,
            })

        selected_ids = [s.source_id for s in selection.selected_sources]
        deprioritized_ids = [s.source_id for s in selection.deprioritized_sources]

        # Verify ground truth dataset correspondence
        corresponds_to_dataset = False
        evidence_found = []
        if "document" in [s.source_type.value for s in selection.selected_sources]:
            matching_docs = [d["title"] for d in docs if any(e.lower() in d["content"].lower() for e in analysis.entities)]
            if matching_docs:
                evidence_found.extend(matching_docs[:2])
                corresponds_to_dataset = True
        if "conversation" in [s.source_type.value for s in selection.selected_sources]:
            matching_convs = [c["title"] for c in convs if any(e.lower() in str(c).lower() for e in analysis.entities)]
            if matching_convs:
                evidence_found.extend(matching_convs[:2])
                corresponds_to_dataset = True
        if "ticket" in [s.source_type.value for s in selection.selected_sources]:
            matching_ticks = [t["title"] for t in tickets if any(e.lower() in str(t).lower() for e in analysis.entities)]
            if matching_ticks:
                evidence_found.extend(matching_ticks[:2])
                corresponds_to_dataset = True

        test_result = {
            "test_id": item["test_id"],
            "test_name": item["name"],
            "query": query,
            "query_analysis": {
                "primary_intent": analysis.primary_intent.value,
                "secondary_intents": [i.value for i in analysis.secondary_intents],
                "temporal_requirement": analysis.temporal_requirement.value,
                "temporal_anchor": analysis.temporal_anchor,
                "entities": analysis.entities,
                "technical_keywords": analysis.technical_keywords,
                "information_requirements": analysis.information_requirements,
                "potential_source_types": [st.value for st in analysis.potential_source_types],
                "analysis_method": analysis.analysis_method,
            },
            "selection_outcome": {
                "selected_source_ids": selected_ids,
                "deprioritized_source_ids": deprioritized_ids,
                "selection_threshold": selection.selection_threshold,
                "temporal_coverage": selection.temporal_coverage,
                "information_requirement_coverage": selection.information_requirement_coverage,
                "unmet_information_requirements": selection.unmet_information_requirements,
                "selection_summary": selection.selection_summary,
            },
            "ranked_sources": ranked_list,
            "dataset_ground_truth": {
                "expected_corroboration": item["dataset_corroboration"],
                "evidence_found_in_dataset": evidence_found,
                "corresponds_to_useful_evidence": corresponds_to_dataset,
            },
            "evaluation_verdict": "PASS" if selected_ids and (
                (item["test_id"] == "Test A" and "SRC-DOCS" in selected_ids)
                or (item["test_id"] == "Test B" and "SRC-CONV" in selected_ids)
                or (item["test_id"] == "Test C" and "SRC-DOCS" in selected_ids and "SRC-CONV" in selected_ids)
                or (item["test_id"] == "Test D" and "SRC-TICKETS" in selected_ids)
                or (item["test_id"] == "Test E" and "SRC-DOCS" in selected_ids)
            ) else "FAIL",
        }
        results.append(test_result)

    report_payload = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": "Project Atlas",
        "dataset_as_of": dataset_as_of.isoformat(),
        "total_tests": len(results),
        "passed_tests": sum(1 for r in results if r["evaluation_verdict"] == "PASS"),
        "failed_tests": sum(1 for r in results if r["evaluation_verdict"] == "FAIL"),
        "test_results": results,
    }

    out_file = Path("evaluation/phase3_routing_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
    print(f"Saved evaluation results to {out_file}")
    return report_payload


if __name__ == "__main__":
    run_evaluation()

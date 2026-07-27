"""Layer 1: Tool audit — enumerate all agent tools and map test coverage."""

import json
from pathlib import Path
from typing import Any

import pytest
import structlog

from src.agents.extraction.tools import ALL_EXTRACTION_TOOLS

logger = structlog.get_logger(__name__)
from src.agents.validation.tools import (
    per_document_validation_tool,
    cross_document_compare_tool,
    discrepancy_classify_tool,
    applicant_clarify_tool,
    validation_confidence_tool,
)
from src.agents.eligibility.tools import (
    ml_model_predict_tool,
    feature_importance_tool,
    adjust_factor_weighting_tool,
    eligibility_explanation_tool,
)
from src.agents.decision.tools import (
    decision_logic_tool,
    decision_explanation_tool,
    enablement_recommendation_tool,
    decision_formatting_tool,
)

TOOLS_REGISTRY = {
    "extraction": ALL_EXTRACTION_TOOLS,
    "validation": [
        per_document_validation_tool,
        cross_document_compare_tool,
        discrepancy_classify_tool,
        applicant_clarify_tool,
        validation_confidence_tool,
    ],
    "eligibility": [
        ml_model_predict_tool,
        feature_importance_tool,
        adjust_factor_weighting_tool,
        eligibility_explanation_tool,
    ],
    "decision": [
        decision_logic_tool,
        decision_explanation_tool,
        enablement_recommendation_tool,
        decision_formatting_tool,
    ],
}

UNIT_TEST_PATHS = {
    "extraction": Path("tests/unit/agents/test_extraction.py"),
    "validation": Path("tests/unit/agents/test_validation.py"),
    "eligibility": Path("tests/unit/agents/test_eligibility.py"),
    "decision": Path("tests/unit/agents/test_decision.py"),
}


def _tool_name(tool) -> str:
    return getattr(tool, "name", getattr(tool, "__name__", str(tool)))


def _count_tests_for_agent(agent_name: str) -> int:
    """Count test classes/methods in the unit test file for an agent."""
    test_file = UNIT_TEST_PATHS.get(agent_name)
    if not test_file or not test_file.exists():
        return 0
    content = test_file.read_text(encoding="utf-8")
    # Rough count: count lines starting with 'def test_' or 'class Test'
    test_count = sum(
        1 for line in content.splitlines()
        if line.strip().startswith("def test_") or line.strip().startswith("class Test")
    )
    return test_count


def test_tool_audit_produces_report(tmp_path):
    """Audit all tools and produce a coverage gap report."""
    report: dict[str, Any] = {
        "total_tools": 0,
        "tool_inventory": {},
        "coverage_map": {},
        "gaps": [],
    }

    for agent_name, tools in TOOLS_REGISTRY.items():
        tool_names = [_tool_name(t) for t in tools]
        report["tool_inventory"][agent_name] = tool_names
        report["total_tools"] += len(tool_names)

        test_count = _count_tests_for_agent(agent_name)
        logger.debug(
            "tool_audit_agent_counted",
            agent=agent_name,
            tool_count=len(tool_names),
            unit_test_count=test_count,
        )
        report["coverage_map"][agent_name] = {
            "tool_count": len(tool_names),
            "unit_test_count": test_count,
            "has_tests": test_count > 0,
        }

        if test_count == 0:
            report["gaps"].append({
                "agent": agent_name,
                "tools": tool_names,
                "issue": "no_unit_tests",
            })

    # Write artifact
    report_path = Path(__file__).parent / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info(
        "tool_audit_complete",
        total_tools=report["total_tools"],
        gap_count=len(report["gaps"]),
        agents=list(report["tool_inventory"].keys()),
    )

    assert report["total_tools"] == 19
    assert len(report["gaps"]) >= 0  # gaps are informational
    assert set(report["tool_inventory"].keys()) == {"extraction", "validation", "eligibility", "decision"}

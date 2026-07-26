"""End-to-end system test for eligibility agent with real test data."""

import json
from pathlib import Path

import pytest

from src.agents.eligibility.graph import get_eligibility_graph


@pytest.mark.asyncio
async def test_eligibility_agent_e2e_divorced_employed():
    """Test eligibility agent end-to-end with divorced_employed_good_credit profile."""
    # Load test profile
    profile_path = Path("data/test_applicants/divorced_employed_good_credit/profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    
    # Build extracted_data from profile
    extracted_data = {
        "emirates_id": profile_data["documents"]["emirates_id"]["data"],
        "bank_statement": profile_data["documents"]["bank_statement"]["data"],
        "credit_report": profile_data["documents"]["credit_report"]["data"],
        "application_form": profile_data["documents"]["application_form"]["data"],
    }
    
    # Build initial state
    initial_state = {
        "messages": [],
        "current_phase": "processing",
        "applicant_id": "test-applicant-divorced-001",
        "application_id": "test-application-divorced-001",
        "uploaded_files": [],
        "eligibility_score": None,
        "decision": None,
        "decision_explanation": None,
        "uploaded_documents": [],
        "discrepancies": [],
        "extracted_data": extracted_data,
        "validation_errors": [],
        "identity_number": profile_data["applicant"]["identity_number"],
        "support_category": profile_data["applicant"]["support_category"],
        "extraction_confidence": {
            "emirates_id": 0.95,
            "bank_statement": 0.92,
            "credit_report": 0.90,
            "application_form": 0.88,
        },
        "validation_results": {
            "emirates_id": {"confidence": 0.95},
            "bank_statement": {"confidence": 0.92},
            "credit_report": {"confidence": 0.90},
            "application_form": {"confidence": 0.88},
        },
        "eligibility_factors": None,
        "gate_status": "pending",
        "gate_errors": [],
        "retry_count": 0,
        "escalation_reason": None,
    }
    
    # Run eligibility graph
    graph = get_eligibility_graph()
    final_state = await graph.ainvoke(initial_state)
    
    # Verify results
    assert final_state["eligibility_score"] is not None
    assert 0.0 <= final_state["eligibility_score"] <= 1.0
    assert final_state["gate_status"] == "passed"
    assert final_state["eligibility_factors"] is not None
    assert len(final_state["messages"]) > 0
    
    # Verify expected decision (approved)
    # Note: The actual decision is made by the decision agent, but eligibility score should be high
    assert final_state["eligibility_score"] >= 0.60, (
        f"Expected eligibility score >= 0.60 for approved profile, got {final_state['eligibility_score']}"
    )
    
    print(f"✓ Eligibility score: {final_state['eligibility_score']:.2f}")
    print(f"✓ Gate status: {final_state['gate_status']}")
    print(f"✓ Eligibility factors: {list(final_state['eligibility_factors'].keys())}")


@pytest.mark.asyncio
async def test_eligibility_agent_e2e_abandoned_unemployed():
    """Test eligibility agent end-to-end with abandoned_unemployed_poor_credit profile."""
    # Load test profile
    profile_path = Path("data/test_applicants/abandoned_unemployed_poor_credit/profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    
    # Build extracted_data from profile
    extracted_data = {
        "emirates_id": profile_data["documents"]["emirates_id"]["data"],
        "bank_statement": profile_data["documents"]["bank_statement"]["data"],
        "credit_report": profile_data["documents"]["credit_report"]["data"],
        "application_form": profile_data["documents"]["application_form"]["data"],
    }
    
    # Build initial state
    initial_state = {
        "messages": [],
        "current_phase": "processing",
        "applicant_id": "test-applicant-abandoned-001",
        "application_id": "test-application-abandoned-001",
        "uploaded_files": [],
        "eligibility_score": None,
        "decision": None,
        "decision_explanation": None,
        "uploaded_documents": [],
        "discrepancies": [],
        "extracted_data": extracted_data,
        "validation_errors": [],
        "identity_number": profile_data["applicant"]["identity_number"],
        "support_category": profile_data["applicant"]["support_category"],
        "extraction_confidence": {
            "emirates_id": 0.93,
            "bank_statement": 0.91,
            "credit_report": 0.89,
            "application_form": 0.87,
        },
        "validation_results": {
            "emirates_id": {"confidence": 0.93},
            "bank_statement": {"confidence": 0.91},
            "credit_report": {"confidence": 0.89},
            "application_form": {"confidence": 0.87},
        },
        "eligibility_factors": None,
        "gate_status": "pending",
        "gate_errors": [],
        "retry_count": 0,
        "escalation_reason": None,
    }
    
    # Run eligibility graph
    graph = get_eligibility_graph()
    final_state = await graph.ainvoke(initial_state)
    
    # Verify results
    assert final_state["eligibility_score"] is not None
    assert 0.0 <= final_state["eligibility_score"] <= 1.0
    assert final_state["gate_status"] == "passed"
    assert final_state["eligibility_factors"] is not None
    assert len(final_state["messages"]) > 0
    
    # For abandoned/unemployed with poor credit, score should be moderate
    # (support category helps, but poor credit and unemployment hurt)
    assert 0.40 <= final_state["eligibility_score"] <= 0.70, (
        f"Expected moderate eligibility score for abandoned/unemployed profile, got {final_state['eligibility_score']}"
    )
    
    print(f"✓ Eligibility score: {final_state['eligibility_score']:.2f}")
    print(f"✓ Gate status: {final_state['gate_status']}")
    print(f"✓ Eligibility factors: {list(final_state['eligibility_factors'].keys())}")


@pytest.mark.asyncio
async def test_eligibility_agent_e2e_unknown_parentage():
    """Test eligibility agent end-to-end with unknown_parentage_self_employed_borderline profile."""
    # Load test profile
    profile_path = Path("data/test_applicants/unknown_parentage_self_employed_borderline/profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    
    # Build extracted_data from profile
    extracted_data = {
        "emirates_id": profile_data["documents"]["emirates_id"]["data"],
        "bank_statement": profile_data["documents"]["bank_statement"]["data"],
        "credit_report": profile_data["documents"]["credit_report"]["data"],
        "application_form": profile_data["documents"]["application_form"]["data"],
    }
    
    # Build initial state
    initial_state = {
        "messages": [],
        "current_phase": "processing",
        "applicant_id": "test-applicant-unknown-001",
        "application_id": "test-application-unknown-001",
        "uploaded_files": [],
        "eligibility_score": None,
        "decision": None,
        "decision_explanation": None,
        "uploaded_documents": [],
        "discrepancies": [],
        "extracted_data": extracted_data,
        "validation_errors": [],
        "identity_number": profile_data["applicant"]["identity_number"],
        "support_category": profile_data["applicant"]["support_category"],
        "extraction_confidence": {
            "emirates_id": 0.94,
            "bank_statement": 0.90,
            "credit_report": 0.88,
            "application_form": 0.86,
        },
        "validation_results": {
            "emirates_id": {"confidence": 0.94},
            "bank_statement": {"confidence": 0.90},
            "credit_report": {"confidence": 0.88},
            "application_form": {"confidence": 0.86},
        },
        "eligibility_factors": None,
        "gate_status": "pending",
        "gate_errors": [],
        "retry_count": 0,
        "escalation_reason": None,
    }
    
    # Run eligibility graph
    graph = get_eligibility_graph()
    final_state = await graph.ainvoke(initial_state)
    
    # Verify results
    assert final_state["eligibility_score"] is not None
    assert 0.0 <= final_state["eligibility_score"] <= 1.0
    assert final_state["gate_status"] == "passed"
    assert final_state["eligibility_factors"] is not None
    assert len(final_state["messages"]) > 0
    
    # For unknown parentage with self-employment and borderline credit, score should be moderate
    assert 0.45 <= final_state["eligibility_score"] <= 0.75, (
        f"Expected moderate eligibility score for unknown parentage profile, got {final_state['eligibility_score']}"
    )
    
    print(f"✓ Eligibility score: {final_state['eligibility_score']:.2f}")
    print(f"✓ Gate status: {final_state['gate_status']}")
    print(f"✓ Eligibility factors: {list(final_state['eligibility_factors'].keys())}")

"""Test state reducers."""
import operator
from src.agents.state import ApplicantState


def test_uploaded_documents_reducer():
    """Test that uploaded_documents uses add reducer."""
    state_type = ApplicantState.__annotations__["uploaded_documents"]
    # Check that it's Annotated with operator.add
    assert hasattr(state_type, "__metadata__")
    assert operator.add in state_type.__metadata__


def test_discrepancies_reducer():
    """Test that discrepancies uses add reducer."""
    state_type = ApplicantState.__annotations__["discrepancies"]
    assert hasattr(state_type, "__metadata__")
    assert operator.add in state_type.__metadata__


def test_validation_errors_reducer():
    """Test that validation_errors uses add reducer."""
    state_type = ApplicantState.__annotations__["validation_errors"]
    assert hasattr(state_type, "__metadata__")
    assert operator.add in state_type.__metadata__


def test_uploaded_files_reducer():
    """Test that uploaded_files uses add reducer."""
    state_type = ApplicantState.__annotations__["uploaded_files"]
    assert hasattr(state_type, "__metadata__")
    assert operator.add in state_type.__metadata__


def test_gate_errors_reducer():
    """Test that gate_errors uses add reducer."""
    state_type = ApplicantState.__annotations__["gate_errors"]
    assert hasattr(state_type, "__metadata__")
    assert operator.add in state_type.__metadata__


def test_extraction_results_reducer():
    """Test that extraction_results uses add reducer."""
    state_type = ApplicantState.__annotations__["extraction_results"]
    assert hasattr(state_type, "__metadata__")
    assert operator.add in state_type.__metadata__


def test_clarification_questions_reducer():
    """Test that _clarification_questions uses add reducer."""
    state_type = ApplicantState.__annotations__["_clarification_questions"]
    assert hasattr(state_type, "__metadata__")
    assert operator.add in state_type.__metadata__


def test_enablement_recommendations_reducer():
    """Test that enablement_recommendations uses add reducer."""
    state_type = ApplicantState.__annotations__["enablement_recommendations"]
    assert hasattr(state_type, "__metadata__")
    assert operator.add in state_type.__metadata__

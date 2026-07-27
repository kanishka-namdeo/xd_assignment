"""Unit tests for src.services.agent_runner streaming and non-streaming execution."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.agent_runner import run, run_streaming, _process_stream_event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_input_data(**overrides) -> dict:
    base = {
        "application_id": "app-001",
        "applicant_id": "appl-001",
        "current_phase": "intake",
        "messages": [],
        "uploaded_files": [],
    }
    base.update(overrides)
    return base


def _mock_graph():
    """Return a mock compiled graph with astream and ainvoke."""
    graph = MagicMock()
    graph.astream = MagicMock()  # Will be set to return async generators per-test
    graph.ainvoke = AsyncMock()
    return graph


def _set_astream_events(graph, events: list[dict]):
    """Configure graph.astream to return an async iterator over the given events."""
    async def _async_iter():
        for event in events:
            yield event
    graph.astream.return_value = _async_iter()


# ---------------------------------------------------------------------------
# run_streaming – phase transitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_streaming_yields_phase_transitions():
    """run_streaming yields phase_transition events when current_phase changes."""
    graph = _mock_graph()

    # Simulate two node outputs with different phases
    events_to_stream = [
        {"intake": {"current_phase": "intake", "messages": []}},
        {"document_collection": {"current_phase": "document_collection", "messages": []}},
        {"processing": {"current_phase": "processing", "messages": []}},
    ]
    _set_astream_events(graph, events_to_stream)

    with (
        patch("src.services.agent_runner.build_orchestrator_graph", return_value=graph),
        patch("src.services.agent_runner.LLMClient"),
        patch("src.services.agent_runner.inject_llm_client"),
        patch("src.services.agent_runner.propagate_attributes", create=True) as mock_prop,
    ):
        # propagate_attributes is imported inside the function, so we patch it at the module level
        import src.services.agent_runner as mod
        with patch.object(mod, "propagate_attributes", create=True, side_effect=lambda **kw: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)):
            events = []
            async for event in run_streaming(_make_input_data(current_phase="authentication")):
                events.append(event)

    phase_events = [e for e in events if e["type"] == "phase_transition"]
    # Should have transitions for intake, document_collection, processing
    # (authentication is the starting phase so it won't trigger a transition)
    phases_seen = [e["phase"] for e in phase_events]
    assert "intake" in phases_seen
    assert "document_collection" in phases_seen
    assert "processing" in phases_seen


@pytest.mark.asyncio
async def test_streaming_yields_extraction_complete():
    """run_streaming yields extraction_complete when extraction_results appear."""
    graph = _mock_graph()

    events_to_stream = [
        {"processing": {
            "current_phase": "processing",
            "extraction_results": [{"doc": "a"}, {"doc": "b"}],
        }}
    ]
    _set_astream_events(graph, events_to_stream)

    with (
        patch("src.services.agent_runner.build_orchestrator_graph", return_value=graph),
        patch("src.services.agent_runner.LLMClient"),
        patch("src.services.agent_runner.inject_llm_client"),
    ):
        import src.services.agent_runner as mod
        with patch.object(mod, "propagate_attributes", create=True, side_effect=lambda **kw: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)):
            events = []
            async for event in run_streaming(_make_input_data()):
                events.append(event)

    extraction_events = [e for e in events if e["type"] == "extraction_complete"]
    assert len(extraction_events) == 1
    assert extraction_events[0]["document_count"] == 2
    assert "duration_ms" in extraction_events[0]


@pytest.mark.asyncio
async def test_streaming_yields_validation_complete():
    """run_streaming yields validation_complete when validation_results appear."""
    graph = _mock_graph()

    events_to_stream = [
        {"review": {
            "current_phase": "review",
            "validation_results": {"status": "pass"},
            "validation_confidence": 0.92,
        }}
    ]
    _set_astream_events(graph, events_to_stream)

    with (
        patch("src.services.agent_runner.build_orchestrator_graph", return_value=graph),
        patch("src.services.agent_runner.LLMClient"),
        patch("src.services.agent_runner.inject_llm_client"),
    ):
        import src.services.agent_runner as mod
        with patch.object(mod, "propagate_attributes", create=True, side_effect=lambda **kw: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)):
            events = []
            async for event in run_streaming(_make_input_data()):
                events.append(event)

    validation_events = [e for e in events if e["type"] == "validation_complete"]
    assert len(validation_events) == 1
    assert validation_events[0]["confidence"] == 0.92


@pytest.mark.asyncio
async def test_streaming_yields_decision_reached():
    """run_streaming yields decision_reached when decision appears."""
    graph = _mock_graph()

    events_to_stream = [
        {"decision": {
            "current_phase": "decision",
            "decision": "approved",
        }}
    ]
    _set_astream_events(graph, events_to_stream)

    with (
        patch("src.services.agent_runner.build_orchestrator_graph", return_value=graph),
        patch("src.services.agent_runner.LLMClient"),
        patch("src.services.agent_runner.inject_llm_client"),
    ):
        import src.services.agent_runner as mod
        with patch.object(mod, "propagate_attributes", create=True, side_effect=lambda **kw: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)):
            events = []
            async for event in run_streaming(_make_input_data()):
                events.append(event)

    decision_events = [e for e in events if e["type"] == "decision_reached"]
    assert len(decision_events) == 1
    assert decision_events[0]["decision"] == "approved"


@pytest.mark.asyncio
async def test_streaming_yields_eligibility_scored():
    """run_streaming yields eligibility_scored when eligibility_score appears."""
    graph = _mock_graph()

    events_to_stream = [
        {"processing": {
            "current_phase": "processing",
            "eligibility_score": 0.78,
        }}
    ]
    _set_astream_events(graph, events_to_stream)

    with (
        patch("src.services.agent_runner.build_orchestrator_graph", return_value=graph),
        patch("src.services.agent_runner.LLMClient"),
        patch("src.services.agent_runner.inject_llm_client"),
    ):
        import src.services.agent_runner as mod
        with patch.object(mod, "propagate_attributes", create=True, side_effect=lambda **kw: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)):
            events = []
            async for event in run_streaming(_make_input_data()):
                events.append(event)

    score_events = [e for e in events if e["type"] == "eligibility_scored"]
    assert len(score_events) == 1
    assert score_events[0]["score"] == 0.78


# ---------------------------------------------------------------------------
# run_streaming – interrupts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_streaming_handles_interrupts():
    """run_streaming yields an interrupt event when __interrupt__ is present."""
    graph = _mock_graph()

    events_to_stream = [
        {"intake": {
            "current_phase": "intake",
            "__interrupt__": {"question": "Please upload your ID"},
        }}
    ]
    _set_astream_events(graph, events_to_stream)

    with (
        patch("src.services.agent_runner.build_orchestrator_graph", return_value=graph),
        patch("src.services.agent_runner.LLMClient"),
        patch("src.services.agent_runner.inject_llm_client"),
    ):
        import src.services.agent_runner as mod
        with patch.object(mod, "propagate_attributes", create=True, side_effect=lambda **kw: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)):
            events = []
            async for event in run_streaming(_make_input_data()):
                events.append(event)

    interrupt_events = [e for e in events if e["type"] == "interrupt"]
    assert len(interrupt_events) == 1
    assert interrupt_events[0]["interrupt_data"] == {"question": "Please upload your ID"}


# ---------------------------------------------------------------------------
# run_streaming – completion event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_streaming_yields_complete_event():
    """run_streaming always yields a 'complete' event at the end."""
    graph = _mock_graph()

    events_to_stream = [
        {"enablement": {"current_phase": "enablement"}}
    ]
    _set_astream_events(graph, events_to_stream)

    with (
        patch("src.services.agent_runner.build_orchestrator_graph", return_value=graph),
        patch("src.services.agent_runner.LLMClient"),
        patch("src.services.agent_runner.inject_llm_client"),
    ):
        import src.services.agent_runner as mod
        with patch.object(mod, "propagate_attributes", create=True, side_effect=lambda **kw: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)):
            events = []
            async for event in run_streaming(_make_input_data()):
                events.append(event)

    assert events[-1]["type"] == "complete"
    assert "duration_ms" in events[-1]


# ---------------------------------------------------------------------------
# run_streaming – resume with Command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_streaming_resume_uses_command():
    """run_streaming uses Command(resume=...) when resume payload is present."""
    graph = _mock_graph()

    events_to_stream = [
        {"document_collection": {"current_phase": "document_collection"}}
    ]
    _set_astream_events(graph, events_to_stream)

    with (
        patch("src.services.agent_runner.build_orchestrator_graph", return_value=graph),
        patch("src.services.agent_runner.LLMClient"),
        patch("src.services.agent_runner.inject_llm_client"),
    ):
        import src.services.agent_runner as mod
        with patch.object(mod, "propagate_attributes", create=True, side_effect=lambda **kw: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)):
            events = []
            async for event in run_streaming(_make_input_data(resume={"answer": "yes"})):
                events.append(event)

    # Verify astream was called (not ainvoke)
    graph.astream.assert_called_once()
    call_args = graph.astream.call_args
    # First arg should be a Command
    from langgraph.types import Command
    assert isinstance(call_args[0][0], Command)


# ---------------------------------------------------------------------------
# run_streaming – error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_streaming_propagates_errors():
    """run_streaming raises exceptions and logs them."""
    graph = _mock_graph()

    async def fake_astream(*args, **kwargs):
        if False:
            yield  # make it an async generator
        raise RuntimeError("graph failure")

    graph.astream.return_value = fake_astream()

    with (
        patch("src.services.agent_runner.build_orchestrator_graph", return_value=graph),
        patch("src.services.agent_runner.LLMClient"),
        patch("src.services.agent_runner.inject_llm_client"),
    ):
        import src.services.agent_runner as mod
        with patch.object(mod, "propagate_attributes", create=True, side_effect=lambda **kw: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)):
            with pytest.raises(RuntimeError, match="graph failure"):
                async for _ in run_streaming(_make_input_data()):
                    pass


# ---------------------------------------------------------------------------
# run() – backward compatibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_still_uses_ainvoke():
    """run() still uses ainvoke() and returns the full result dict."""
    graph = _mock_graph()
    expected_result = {
        "current_phase": "enablement",
        "decision": "approved",
        "extraction_results": [],
    }
    graph.ainvoke.return_value = expected_result

    with (
        patch("src.services.agent_runner.build_orchestrator_graph", return_value=graph),
        patch("src.services.agent_runner.LLMClient"),
        patch("src.services.agent_runner.inject_llm_client"),
        patch("src.services.agent_runner.persist_results", new_callable=AsyncMock),
    ):
        import src.services.agent_runner as mod
        with patch.object(mod, "propagate_attributes", create=True, side_effect=lambda **kw: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)):
            result = await run(_make_input_data())

    assert result == expected_result
    graph.ainvoke.assert_called_once()
    graph.astream.assert_not_called()


# ---------------------------------------------------------------------------
# _process_stream_event – unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_stream_event_phase_transition():
    """_process_stream_event yields phase_transition for new phases."""
    event = {"intake": {"current_phase": "intake"}}
    events = []
    async for e in _process_stream_event(event, last_phase="authentication", start_ms=0.0, thread_id="t1"):
        events.append(e)

    assert len(events) == 1
    assert events[0]["type"] == "phase_transition"
    assert events[0]["phase"] == "intake"


@pytest.mark.asyncio
async def test_process_stream_event_skips_same_phase():
    """_process_stream_event does NOT yield phase_transition if phase hasn't changed."""
    event = {"intake": {"current_phase": "intake"}}
    events = []
    async for e in _process_stream_event(event, last_phase="intake", start_ms=0.0, thread_id="t1"):
        events.append(e)

    phase_events = [e for e in events if e["type"] == "phase_transition"]
    assert len(phase_events) == 0


@pytest.mark.asyncio
async def test_process_stream_event_non_dict_skipped():
    """_process_stream_event skips non-dict state updates."""
    event = {"node": "not_a_dict"}
    events = []
    async for e in _process_stream_event(event, last_phase=None, start_ms=0.0, thread_id="t1"):
        events.append(e)

    assert len(events) == 0


@pytest.mark.asyncio
async def test_process_stream_event_multiple_key_events():
    """_process_stream_event yields multiple events from a single state update."""
    event = {"processing": {
        "current_phase": "processing",
        "extraction_results": [{"a": 1}],
        "eligibility_score": 0.85,
    }}
    events = []
    async for e in _process_stream_event(event, last_phase="document_collection", start_ms=0.0, thread_id="t1"):
        events.append(e)

    types = [e["type"] for e in events]
    assert "phase_transition" in types
    assert "extraction_complete" in types
    assert "eligibility_scored" in types
    # All events should have duration_ms
    for e in events:
        assert "duration_ms" in e
        assert "timestamp" in e

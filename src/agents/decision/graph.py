"""Decision subgraph definition using LangGraph StateGraph."""

from langgraph.graph import END, StateGraph

from src.agents.decision.nodes import decision_react_node, synthesize_decision_node
from src.agents.decision.routes import should_use_react
from src.agents.state import ApplicantState


def build_decision_graph() -> StateGraph:
    """Build the decision subgraph.

    The graph has two paths:
    1. ReAct agent path - Uses LLM reasoning with 4 decision tools
    2. Deterministic path - Applies decision rules directly

    Both paths return:
    - decision: "approved" | "soft_decline" | "manual_review"
    - decision_explanation: Human-readable explanation
    - enablement_recommendations: Personalized recommendations (optional)
    """
    workflow = StateGraph(ApplicantState)

    workflow.add_node("decision_react", decision_react_node)
    workflow.add_node("decision_deterministic", synthesize_decision_node)

    workflow.set_conditional_entry_point(
        should_use_react,
        {
            "react": "decision_react",
            "deterministic": "decision_deterministic",
        },
    )

    workflow.add_edge("decision_react", END)
    workflow.add_edge("decision_deterministic", END)

    return workflow


def get_decision_agent():
    """Factory function to get a compiled decision agent.

    Returns a fresh compiled agent instance to avoid module-level initialization issues.
    """
    graph = build_decision_graph()
    return graph.compile()

"""LangGraph agent execution wrapper."""

from src.agents.orchestrator.graph import build_orchestrator_graph


async def run(input_data: dict) -> dict:
    graph = build_orchestrator_graph()
    result = await graph.ainvoke(input_data)
    return result

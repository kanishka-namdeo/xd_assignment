"""7-phase node functions - re-exported from phases/ for backward compatibility.

All node implementations have been decomposed into individual phase modules.
This module exists solely to maintain backward-compatible imports.
"""

import structlog

from src.agents.orchestrator.di import (
    _get_llm_client,
    get_services,
    inject_llm_client,
    inject_services,
)
from src.agents.orchestrator.phases.authentication import authentication_node
from src.agents.orchestrator.phases.decision import decision_node
from src.agents.orchestrator.phases.document_collection import document_collection_node
from src.agents.orchestrator.phases.enablement import enablement_node
from src.agents.orchestrator.phases.intake import intake_node
from src.agents.orchestrator.phases.processing import processing_node
from src.agents.orchestrator.phases.review import review_node

logger = structlog.get_logger(__name__)

__all__ = [
    "authentication_node",
    "intake_node",
    "document_collection_node",
    "processing_node",
    "review_node",
    "decision_node",
    "enablement_node",
    "inject_services",
    "inject_llm_client",
    "get_services",
    "_get_llm_client",
]

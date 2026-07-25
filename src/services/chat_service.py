"""Chat session management."""

from datetime import datetime, timezone

import structlog

from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.services.agent_runner import run as run_orchestrator

logger = structlog.get_logger(__name__)


async def handle_chat(
    db_session,
    application_id: str,
    text: str,
    file_paths: list[str],
) -> dict:
    """Handle a chat message and route through the orchestrator."""
    start = datetime.now(timezone.utc)
    logger.info(
        "chat_message_received",
        application_id=application_id,
        file_count=len(file_paths),
    )

    application_repo = ApplicationRepository(db_session)
    application = await application_repo.get_by_id(application_id)

    if application is None:
        logger.warning("application_not_found", application_id=application_id)
        raise ValueError(f"Application {application_id} not found")

    previous_phase = application.current_phase

    try:
        result = await run_orchestrator(
            {
                "messages": [{"role": "user", "content": text}],
                "current_phase": application.current_phase,
                "applicant_id": str(application.applicant_id),
                "application_id": str(application.id),
                "uploaded_files": file_paths,
            }
        )
    except Exception as e:
        logger.exception("orchestrator_invocation_failed", application_id=application_id, error=str(e))
        raise

    new_phase = result.get("current_phase", application.current_phase)
    application.current_phase = new_phase
    await application_repo.update(application)

    duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

    if new_phase != previous_phase:
        logger.info(
            "phase_transition",
            application_id=application_id,
            previous_phase=previous_phase,
            new_phase=new_phase,
        )

    logger.info(
        "chat_response_sent",
        application_id=application_id,
        phase=new_phase,
        has_decision=result.get("decision") is not None,
        duration_ms=round(duration_ms, 2),
    )

    return {
        "message": result["messages"][-1]["content"],
        "phase": new_phase,
        "uploaded_documents": result.get("uploaded_documents", []),
        "decision": result.get("decision"),
    }

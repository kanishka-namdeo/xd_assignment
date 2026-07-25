"""Chat session management."""

from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.services.agent_runner import run as run_orchestrator


async def handle_chat(
    db_session,
    application_id: str,
    text: str,
    file_paths: list[str],
) -> dict:
    application_repo = ApplicationRepository(db_session)
    application = await application_repo.get_by_id(application_id)

    if application is None:
        raise ValueError(f"Application {application_id} not found")

    result = await run_orchestrator(
        {
            "messages": [{"role": "user", "content": text}],
            "current_phase": application.current_phase,
            "applicant_id": str(application.applicant_id),
            "application_id": str(application.id),
            "uploaded_files": file_paths,
        }
    )

    application.current_phase = result.get("current_phase", application.current_phase)
    await application_repo.update(application)

    return {
        "message": result["messages"][-1]["content"],
        "phase": result.get("current_phase", application.current_phase),
        "uploaded_documents": result.get("uploaded_documents", []),
        "decision": result.get("decision"),
    }

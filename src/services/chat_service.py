"""Chat session management."""

import time
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.schemas.chat import ChatResponse, InterruptData, UploadedDocument
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.infrastructure.observability.langfuse_client import LangfuseClient
from src.services.agent_runner import run as run_orchestrator
from src.services.decision_service import DecisionService

logger = structlog.get_logger(__name__)

UPLOAD_DIR = Path("data/uploads")


class ChatService:
    """Handle chat interactions and orchestrator coordination."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.application_repo = ApplicationRepository(session)

    async def handle_chat(
        self,
        application_id: str,
        text: str,
        file_paths: list[str],
        langfuse_client: LangfuseClient | None = None,
    ) -> ChatResponse:
        """Process a chat message through the orchestrator and return formatted response.

        Encapsulates state load/save, orchestrator invocation, interrupt handling,
        decision persistence, and phase transitions.

        Args:
            application_id: The application UUID.
            text: User message text.
            file_paths: Paths to uploaded files.
            langfuse_client: Optional Langfuse observability client.

        Returns:
            ChatResponse with message, phase, documents, decision, and recommendations.
        """
        start_ms = time.perf_counter()

        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            logger.warning("application_not_found", application_id=application_id)
            raise ValueError(f"Application {application_id} not found")

        previous_phase = application.current_phase

        # Build graph input from previous state
        previous_state = await self.application_repo.get_state(application.id)
        graph_input: dict[str, Any] = dict(previous_state) if previous_state else {}

        had_pending_interrupt = previous_state and previous_state.get("_pending_interrupt")

        if had_pending_interrupt:
            graph_input["resume"] = text
            graph_input["messages"] = previous_state.get("messages", [])
            logger.info(
                "resuming_from_interrupt",
                application_id=application_id,
                file_count=len(file_paths),
            )
        else:
            graph_input["messages"] = [{"role": "user", "content": text}]

        graph_input["current_phase"] = application.current_phase
        graph_input["applicant_id"] = str(application.applicant_id)
        graph_input["application_id"] = str(application.id)
        graph_input["uploaded_files"] = file_paths

        logger.info(
            "invoking_orchestrator",
            application_id=application_id,
            phase=application.current_phase,
            file_count=len(file_paths),
            has_interrupt=had_pending_interrupt,
        )

        # Invoke orchestrator with exception safety
        try:
            result = await run_orchestrator(graph_input, langfuse_client=langfuse_client)
        except ValidationError as e:
            duration_ms = (time.perf_counter() - start_ms) * 1000
            logger.exception(
                "validation_error_in_orchestrator",
                application_id=application_id,
                phase=application.current_phase,
                error_count=len(e.errors()),
                duration_ms=round(duration_ms, 2),
            )
            error_details = "; ".join(f"{err.get('loc', ['unknown'])}: {err.get('msg', 'validation failed')}" for err in e.errors())
            return ChatResponse(
                message=f"Validation error occurred: {error_details}",
                phase=previous_phase,
                uploaded_documents=[],
                decision=None,
                decision_card=None,
                interrupt=None,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_ms) * 1000
            logger.exception(
                "orchestrator_invocation_failed",
                application_id=application_id,
                phase=application.current_phase,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )
            return ChatResponse(
                message="An error occurred while processing your request. Please try again. If the problem persists, contact support.",
                phase=previous_phase,
                uploaded_documents=[],
                decision=None,
                decision_card=None,
                interrupt=None,
            )

        # DEBUG: Log what the graph returned
        logger.info(
            "orchestrator_result_debug",
            application_id=application_id,
            result_keys=list(result.keys()),
            result_current_phase=result.get("current_phase"),
            result_decision=result.get("decision"),
            result_validation_confidence=result.get("validation_confidence"),
            result_has_interrupt=bool(result.get("__interrupt__")),
        )

        # Handle interrupt
        interrupt_data = None
        if result.get("__interrupt__"):
            interrupt_value = result["__interrupt__"][0].value if isinstance(result["__interrupt__"], list) else result["__interrupt__"].value
            if isinstance(interrupt_value, dict):
                try:
                    interrupt_data = InterruptData(
                        question=interrupt_value.get("question", ""),
                        phase=interrupt_value.get("phase", ""),
                        missing_fields=interrupt_value.get("missing_fields"),
                        missing_documents=interrupt_value.get("missing_documents"),
                        discrepancies=interrupt_value.get("discrepancies"),
                        recommendations=interrupt_value.get("recommendations"),
                    )
                except ValidationError as e:
                    logger.warning(
                        "interrupt_data_validation_failed",
                        application_id=application_id,
                        error_count=len(e.errors()),
                        errors=[err.get("msg") for err in e.errors()],
                    )
                    interrupt_data = InterruptData(
                        question=interrupt_value.get("question", ""),
                        phase=interrupt_value.get("phase", "unknown"),
                    )
            result["_pending_interrupt"] = True
        else:
            result["_pending_interrupt"] = False

        # Persist full state snapshot
        await self.application_repo.save_state(application.id, result)

        # Persist decision if reached
        if result.get("decision") and application_id:
            try:
                decision_svc = DecisionService(self.session)
                await decision_svc.persist_decision(
                    application_id=UUID(application_id),
                    decision=result["decision"],
                    decision_explanation=result.get("decision_explanation", ""),
                    eligibility_score=result.get("eligibility_score", 0.0),
                    eligibility_factors=result.get("eligibility_factors"),
                    validation_confidence=result.get("validation_confidence"),
                )
            except Exception as e:
                logger.exception("decision_persist_failed", application_id=application_id, error=str(e))

        # Update phase
        new_phase = result.get("current_phase", application.current_phase)
        application.current_phase = new_phase
        await self.application_repo.update(application)

        # Build uploaded documents list (deduplicate by file_path)
        seen_paths = set()
        uploaded_documents = []
        for doc in result.get("uploaded_documents", []):
            file_path = doc.get("file_path", "")
            if file_path and file_path not in seen_paths:
                seen_paths.add(file_path)
                uploaded_documents.append(
                    UploadedDocument(
                        doc_type=doc.get("document_type", doc.get("doc_type", "unknown")),
                        file_path=file_path,
                        status=doc.get("status", "uploaded"),
                    )
                )

        # Format decision card if decision reached
        formatted_card = None
        if result.get("decision"):
            try:
                decision_svc = DecisionService(self.session)
                formatted_card = decision_svc.format_decision_card({
                    "decision": result["decision"],
                    "explanation": result.get("decision_explanation", ""),
                    "enablement_recommendations": {"recommendations": result.get("enablement_recommendations", [])},
                    "applicant_context": {
                        "support_category": result.get("applicant_info", {}).get("support_category", "unknown"),
                        "family_size": result.get("applicant_info", {}).get("family_size", 1),
                    },
                })
            except Exception as e:
                logger.warning("decision_formatting_failed", application_id=application_id, error=str(e))

        # Extract message content
        messages = result.get("messages", [])
        message_content = ""
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, "content"):
                message_content = last_msg.content
            elif isinstance(last_msg, dict):
                # Handle both LangChain format (type=human/ai) and standard format (role=user/assistant)
                message_content = last_msg.get("content", "")

        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info(
            "chat_response_complete",
            application_id=application_id,
            phase=new_phase,
            document_count=len(uploaded_documents),
            has_decision=result.get("decision") is not None,
            duration_ms=round(duration_ms, 2),
        )

        return ChatResponse(
            message=message_content,
            phase=new_phase,
            uploaded_documents=uploaded_documents,
            decision=result.get("decision"),
            decision_card=formatted_card,
            interrupt=interrupt_data,
            enablement_recommendations=result.get("enablement_recommendations"),
            discrepancies=result.get("discrepancies"),
        )

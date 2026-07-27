"""Test FastAPI response serialization."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from src.domain.schemas.application import ApplicationResponse
from datetime import datetime
from uuid import uuid4

app = FastAPI()


@app.get("/test", response_model=ApplicationResponse)
async def test_endpoint():
    return ApplicationResponse(
        id=uuid4(),
        applicant_id=uuid4(),
        status="in_progress",
        current_phase="enablement",
        eligibility_score=0.5,
        validation_confidence=0.45,
        decision="manual_review",
        decision_explanation="test",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)

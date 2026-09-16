"""Public upstream curation endpoint."""

from fastapi import APIRouter

from backend.schemas.curation import ClaimSubmission, CurationResult
from backend.services.curation_orchestrator import CurationOrchestrator

router = APIRouter()
_orchestrator = CurationOrchestrator()


@router.post("/curation", response_model=CurationResult)
async def curate_claim(submission: ClaimSubmission) -> CurationResult:
    return await _orchestrator.submit_claim(submission.claim)

"""Schemas owned by the upstream claim-curation pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.messages import EditorVerdict, ProposalDetail, ResearchOutput


class ClaimSubmission(BaseModel):
    claim: str = Field(min_length=3, max_length=4000)


class KnowledgeBaseContext(BaseModel):
    facts: list[str] = Field(default_factory=list)
    duplicate_fact_ids: list[str] = Field(default_factory=list)


class CurationResult(BaseModel):
    proposal_id: str
    claim: str
    kb_context: KnowledgeBaseContext
    research: ResearchOutput
    editor_verdict: EditorVerdict
    review: ProposalDetail
    kb_updated: bool = False
    kb_fact_id: str | None = None

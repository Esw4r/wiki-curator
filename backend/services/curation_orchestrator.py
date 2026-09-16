"""Coordinates Person 1's upstream curation work with the existing Person 2 review boundary."""

from __future__ import annotations

import uuid

from backend.agents.editor_agent import EditorAgent
from backend.agents.research_agent import ResearchAgent
from backend.api.review_routes import submit_for_review
from backend.database import kb_models
from backend.database import models as review_db
from backend.schemas.curation import CurationResult, KnowledgeBaseContext
from backend.schemas.messages import VoteChoice


class CurationOrchestrator:
    def __init__(self, research: ResearchAgent | None = None, editor: EditorAgent | None = None) -> None:
        self._research = research or ResearchAgent()
        self._editor = editor or EditorAgent()

    async def submit_claim(self, claim: str) -> CurationResult:
        proposal_id = f"P-{uuid.uuid4().hex[:8]}"
        facts = await kb_models.find_relevant_facts(claim)
        context = KnowledgeBaseContext(
            facts=[fact["fact_text"] for fact in facts],
            duplicate_fact_ids=[fact["id"] for fact in facts if kb_models.normalize_fact(fact["fact_text"]) == kb_models.normalize_fact(claim)],
        )
        research = await self._research.research(claim, proposal_id)
        # Evidence requires a proposal FK. Create it once; downstream create_proposal is idempotent.
        await review_db.create_proposal(proposal_id, claim)
        await kb_models.store_proposal_evidence(proposal_id, research.sources, query=claim)
        editor_verdict = await self._editor.evaluate(research, context.facts)
        review = await submit_for_review(editor_verdict)
        updated = False
        fact_id: str | None = None
        if review.consensus and review.consensus.decision == VoteChoice.ACCEPT:
            updated, fact_id = await kb_models.accept_fact(
                proposal_id, claim, editor_verdict.supporting_sources, review.consensus.reason,
            )
        return CurationResult(
            proposal_id=proposal_id, claim=claim, kb_context=context, research=research,
            editor_verdict=editor_verdict, review=review, kb_updated=updated, kb_fact_id=fact_id,
        )

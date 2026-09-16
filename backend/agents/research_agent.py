"""Upstream research agent that turns a claim into externally retrieved evidence."""

from __future__ import annotations

import uuid

from backend.schemas.messages import ResearchOutput
from backend.services.search import SearchService


class ResearchAgent:
    def __init__(self, search: SearchService | None = None) -> None:
        self._search = search or SearchService()

    async def research(self, claim: str, proposal_id: str | None = None) -> ResearchOutput:
        proposal_id = proposal_id or f"P-{uuid.uuid4().hex[:8]}"
        # The claim itself is a transparent, reproducible baseline query.
        sources = await self._search.search(claim)
        return ResearchOutput(proposal_id=proposal_id, claim=claim, sources=sources)

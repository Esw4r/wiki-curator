"""Editor Agent: validates research and KB context into the shared EditorVerdict contract."""

from __future__ import annotations

import logging

from backend.config import settings
from backend.schemas.messages import EditorVerdict, EditorVerdictType, ResearchOutput
from backend.services.llm import GroqClient

logger = logging.getLogger(__name__)

_EDITOR_PROMPT = """You are the Editor Agent in a factual knowledge-base curation system.
Evaluate only the supplied claim, research sources, and accepted knowledge-base facts. Do not
invent sources, citations, facts, or conflicts. Return JSON with verdict (VALID, CONTRADICTED,
or INSUFFICIENT_EVIDENCE), confidence (0..1), supporting_source_indexes (zero-based list),
conflicts (list of strings), and reason. VALID needs direct credible support; CONTRADICTED
requires supplied evidence or KB facts that conflict; otherwise choose INSUFFICIENT_EVIDENCE."""


class EditorAgent:
    def __init__(self, llm: GroqClient | None = None) -> None:
        self._llm = llm or GroqClient()

    async def evaluate(self, research: ResearchOutput, kb_facts: list[str]) -> EditorVerdict:
        if not research.sources:
            return EditorVerdict(
                proposal_id=research.proposal_id, claim=research.claim,
                verdict=EditorVerdictType.INSUFFICIENT_EVIDENCE, confidence=0.0,
                reason="No external sources were available for this claim.",
                existing_kb_facts=kb_facts,
            )
        prompt = (
            f"Claim:\n{research.claim}\n\nAccepted KB facts:\n{kb_facts}\n\nSources:\n" +
            "\n".join(f"[{i}] {s.title} | {s.url} | {s.snippet}" for i, s in enumerate(research.sources))
        )
        try:
            data = await self._llm.json_completion(
                model=settings.models.editor, system_prompt=_EDITOR_PROMPT, prompt=prompt,
            )
            verdict = EditorVerdictType(data["verdict"])
            indexes = data.get("supporting_source_indexes", [])
            supporting = [research.sources[i] for i in indexes if isinstance(i, int) and 0 <= i < len(research.sources)]
            return EditorVerdict(
                proposal_id=research.proposal_id, claim=research.claim, verdict=verdict,
                confidence=max(0.0, min(1.0, float(data.get("confidence", 0.0)))),
                supporting_sources=supporting,
                conflicts=[str(item) for item in data.get("conflicts", [])],
                reason=str(data.get("reason", "")), existing_kb_facts=kb_facts,
            )
        except Exception as exc:
            logger.warning("Editor evaluation failed for %s: %s", research.proposal_id, exc)
            return EditorVerdict(
                proposal_id=research.proposal_id, claim=research.claim,
                verdict=EditorVerdictType.INSUFFICIENT_EVIDENCE, confidence=0.0,
                supporting_sources=[], reason="Editor evaluation was unavailable; more evidence is required.",
                existing_kb_facts=kb_facts,
            )

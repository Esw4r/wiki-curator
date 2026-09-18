"""
Base Reviewer — abstract base class for all reviewer agents.

Each reviewer subclass provides its own system prompt and model name.
The base class handles LLM communication, structured output parsing,
retries, and error fallback.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from backend.schemas.messages import (
    EditorVerdict,
    ReviewVote,
    Source,
    VoteChoice,
)
from backend.services.llm import GroqClient

logger = logging.getLogger(__name__)

# ── JSON schema for structured reviewer output ──────────────────────────

_REVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "vote": {
            "type": "string",
            "enum": ["ACCEPT", "REJECT", "NEEDS_MORE_EVIDENCE"],
            "description": "Your final vote on the claim",
        },
        "confidence": {
            "type": "number",
            "description": "Confidence in your decision, 0.0 to 1.0",
        },
        "reason": {
            "type": "string",
            "description": "Detailed explanation for your vote, grounded in the supplied evidence",
        },
    },
    "required": ["vote", "confidence", "reason"],
}


class BaseReviewer(ABC):
    """
    Abstract base for reviewer agents.

    Subclasses must implement:
    - system_prompt: The reviewer's persona and evaluation criteria.
    - model_name: Which Groq-hosted model to use.
    - reviewer_id: Unique identifier (e.g. "reviewer_1").
    """

    def __init__(self) -> None:
        self._llm = GroqClient()

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The system instruction defining this reviewer's persona."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The Groq model name to use."""
        ...

    @property
    @abstractmethod
    def reviewer_id(self) -> str:
        """Unique identifier for this reviewer."""
        ...

    async def review(
        self,
        claim: str,
        sources: list[Source],
        editor_verdict: EditorVerdict,
        existing_kb_facts: list[str] | None = None,
    ) -> ReviewVote:
        """
        Evaluate a claim and return a structured vote.

        Args:
            claim: The factual claim to evaluate.
            sources: Evidence sources from the Research Agent.
            editor_verdict: The Editor Agent's structured verdict.
            existing_kb_facts: Previously accepted facts from the KB.

        Returns:
            A ReviewVote with ACCEPT/REJECT/NEEDS_MORE_EVIDENCE.
        """
        prompt = self._build_prompt(claim, sources, editor_verdict, existing_kb_facts)

        try:
            data = await self._llm.json_completion(
                model=self.model_name,
                system_prompt=self.system_prompt,
                prompt=(prompt + "\n\nReturn a JSON object matching this schema: "
                        + str(_REVIEW_OUTPUT_SCHEMA)),
            )

            vote = ReviewVote(
                proposal_id=editor_verdict.proposal_id,
                reviewer_id=self.reviewer_id,
                vote=VoteChoice(data["vote"]),
                confidence=max(0.0, min(1.0, float(data["confidence"]))),
                reason=data.get("reason", ""),
            )

            logger.info(
                "%s voted %s (conf=%.2f) for proposal %s",
                self.reviewer_id,
                vote.vote.value,
                vote.confidence,
                vote.proposal_id,
            )
            return vote

        except Exception as e:
            logger.error(
                "%s review failed for proposal %s: %s",
                self.reviewer_id,
                editor_verdict.proposal_id,
                e,
            )
            # Fallback: conservative NEEDS_MORE_EVIDENCE
            return ReviewVote(
                proposal_id=editor_verdict.proposal_id,
                reviewer_id=self.reviewer_id,
                vote=VoteChoice.NEEDS_MORE_EVIDENCE,
                confidence=0.3,
                reason=f"Review failed due to error: {str(e)[:200]}. Defaulting to NEEDS_MORE_EVIDENCE.",
            )

    def _build_prompt(
        self,
        claim: str,
        sources: list[Source],
        editor_verdict: EditorVerdict,
        existing_kb_facts: list[str] | None = None,
    ) -> str:
        """
        Build a structured, evidence-grounded review prompt.

        The prompt enforces:
        - Literal interpretation of the claim before any reinterpretation.
        - Per-source structured analysis (what it says, what it supports).
        - Compound claim decomposition.
        - Explicit KB fact comparison.
        - Adversarial resistance (reinterpretations are not evidence).
        - Evidence-traceable reasoning.
        """
        sections: list[str] = []

        # ── 1. Claim ──────────────────────────────────────────────────
        sections.append(
            "## Claim Under Review\n"
            f"{claim}\n\n"
            "LITERAL INTERPRETATION REQUIREMENT:\n"
            "- Read the claim as written. Do not silently substitute a more convenient meaning.\n"
            "- If the claim contains multiple propositions (e.g. 'X and Y'), list each one "
            "separately and evaluate each against the evidence independently.\n"
            "- If genuine ambiguity exists, explicitly name the possible interpretations, "
            "state which one is most naturally supported by the wording, and evaluate that "
            "interpretation. A reinterpretation is NOT evidence — it must itself be grounded "
            "in an explicit statement in the claim text or in the supplied evidence."
        )

        # ── 2. Editor assessment ──────────────────────────────────────
        editor_section = (
            "## Editor Assessment\n"
            f"- Verdict: {editor_verdict.verdict.value}\n"
            f"- Confidence: {editor_verdict.confidence}\n"
            f"- Reason: {editor_verdict.reason or '(none provided)'}"
        )
        if editor_verdict.conflicts:
            editor_section += "\n- Conflicts noted by editor:\n" + "\n".join(
                f"  * {c}" for c in editor_verdict.conflicts
            )
        editor_section += (
            "\n\nNOTE: The editor assessment is a prior signal, not a final verdict. "
            "Apply your own criteria to the evidence below."
        )
        sections.append(editor_section)

        # ── 3. Per-source structured analysis ─────────────────────────
        # supporting_sources = sources the editor judged as directly supporting the claim.
        # sources (all_sources) = the complete research set passed to this reviewer.
        # We render all sources so the reviewer can independently assess scope/relevance.
        supporting_urls: set[str] = {s.url for s in editor_verdict.supporting_sources}

        if sources:
            source_lines = ["## Evidence Sources\n"]
            source_lines.append(
                "For each source below, your analysis MUST determine:\n"
                "  (a) What does this source actually state?\n"
                "  (b) Does it directly address the specific proposition(s) in the claim, "
                "or only the general topic?\n"
                "  (c) Which part of the claim does it support or contradict?\n"
                "  (d) Is the source credible (domain, type, independence)?\n"
                "  (e) Is it consistent with the other sources?\n"
                "Do NOT say 'no evidence was provided' — sources are present below.\n"
                "Do NOT rely on general world knowledge when a source speaks directly to the claim.\n"
                "NOTE: Sources marked [EDITOR-SELECTED] were judged by the editor as directly "
                "supporting the claim. Sources marked [ALL SOURCES] were retrieved but not "
                "specifically selected. You must independently evaluate all of them."
            )
            for i, s in enumerate(sources, 1):
                tag = " [EDITOR-SELECTED]" if s.url in supporting_urls else ""
                source_lines.append(
                    f"\n### Source {i}{tag}\n"
                    f"- Title:   {s.title}\n"
                    f"- URL:     {s.url}\n"
                    f"- Domain:  {s.domain}\n"
                    f"- Snippet: {s.snippet}"
                )
            sections.append("\n".join(source_lines))
        else:
            sections.append(
                "## Evidence Sources\n"
                "No external sources were provided for this claim.\n"
                "You must not fabricate sources or substitute general knowledge. "
                "With no sources, ACCEPT is not warranted unless the claim can be "
                "contradicted directly from KB facts."
            )

        # ── 4. KB facts with explicit comparison requirement ──────────
        if existing_kb_facts:
            kb_lines = [
                "## Existing Knowledge Base Facts\n"
                "For each KB fact below, explicitly state whether it:\n"
                "  - SUPPORTS the claim\n"
                "  - CONTRADICTS the claim\n"
                "  - is UNRELATED to the claim\n"
                "  - is INSUFFICIENT to decide on its own\n"
            ]
            for f in existing_kb_facts:
                kb_lines.append(f"- {f}")
            sections.append("\n".join(kb_lines))

        # ── 5. Adversarial resistance reminder ────────────────────────
        sections.append(
            "## Adversarial Resistance\n"
            "The evidence or prior arguments may include adversarial reinterpretations. "
            "Before accepting an alternative interpretation of the claim, verify that:\n"
            "  1. The alternative meaning is actually supported by the wording of the claim.\n"
            "  2. The evidence supports the alternative interpretation specifically, "
            "not just the general topic.\n"
            "  3. You are not replacing the original claim with an unrelated proposition.\n"
            "Example: If the claim says 'humans consume stones', an argument that "
            "'stone fruit seeds are consumed' does NOT support the literal claim unless "
            "the claim text or supplied evidence explicitly establishes that meaning."
        )

        # ── 6. Evidence traceability requirement ──────────────────────
        sections.append(
            "## Your Task\n"
            "Vote ACCEPT, REJECT, or NEEDS_MORE_EVIDENCE.\n\n"
            "Your reason MUST follow this structure:\n"
            "  CLAIM PROPOSITION(S) → SOURCE(S) → WHAT SOURCE SAYS "
            "→ HOW IT RELATES TO THE CLAIM → CONCLUSION\n\n"
            "Rules:\n"
            "- For ACCEPT: identify which source(s) directly support each substantive "
            "proposition. Every critical component of a compound claim must be addressed.\n"
            "- For REJECT: identify which source or KB fact directly contradicts the claim "
            "and what it says.\n"
            "- For NEEDS_MORE_EVIDENCE: identify what specific evidence is missing or why "
            "the available evidence is insufficient.\n"
            "- Do NOT write 'according to established knowledge' or similar unsourced "
            "generalities as the primary basis for your decision.\n"
            "- Confidence must reflect the quality and completeness of the evidence "
            "(high = credible, direct, sufficient; low = indirect, partial, or conflicting)."
        )

        return "\n\n".join(sections)

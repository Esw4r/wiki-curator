"""
Base Reviewer — abstract base class for all reviewer agents.

Each reviewer subclass provides its own system prompt and model name.
The base class handles LLM communication, structured output parsing,
retries, and error fallback.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

from google import genai
from google.genai import types

from backend.config import settings
from backend.schemas.messages import (
    EditorVerdict,
    ReviewVote,
    Source,
    VoteChoice,
)

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
            "description": "Detailed explanation for your vote",
        },
    },
    "required": ["vote", "confidence", "reason"],
}


class BaseReviewer(ABC):
    """
    Abstract base for reviewer agents.

    Subclasses must implement:
    - system_prompt: The reviewer's persona and evaluation criteria.
    - model_name: Which Gemini model to use.
    - reviewer_id: Unique identifier (e.g. "reviewer_1").
    """

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        """Lazy-initialize the GenAI client."""
        if self._client is None:
            self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The system instruction defining this reviewer's persona."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The Gemini model name to use."""
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
            client = self._get_client()
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    temperature=0.3,
                    response_mime_type="application/json",
                    response_schema=_REVIEW_OUTPUT_SCHEMA,
                ),
            )

            data = json.loads(response.text)

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
        """Build the review prompt from all available context."""
        sections = [
            f"## Claim Under Review\n{claim}",
        ]

        # Editor verdict
        sections.append(
            f"## Editor Assessment\n"
            f"- Verdict: {editor_verdict.verdict.value}\n"
            f"- Confidence: {editor_verdict.confidence}\n"
            f"- Reason: {editor_verdict.reason}"
        )

        # Conflicts
        if editor_verdict.conflicts:
            sections.append(
                f"## Editor-Identified Conflicts\n"
                + "\n".join(f"- {c}" for c in editor_verdict.conflicts)
            )

        # Sources
        if sources:
            source_text = ""
            for i, s in enumerate(sources, 1):
                source_text += (
                    f"\n### Source {i}\n"
                    f"- Title: {s.title}\n"
                    f"- URL: {s.url}\n"
                    f"- Domain: {s.domain}\n"
                    f"- Snippet: {s.snippet}\n"
                )
            sections.append(f"## Evidence Sources{source_text}")
        else:
            sections.append("## Evidence Sources\nNo external sources provided.")

        # Existing KB facts
        if existing_kb_facts:
            sections.append(
                f"## Existing Knowledge Base Facts\n"
                + "\n".join(f"- {f}" for f in existing_kb_facts)
            )

        sections.append(
            "## Your Task\n"
            "Based on the above, provide your vote (ACCEPT, REJECT, or "
            "NEEDS_MORE_EVIDENCE), your confidence (0.0 to 1.0), and "
            "a detailed reason for your decision."
        )

        return "\n\n".join(sections)

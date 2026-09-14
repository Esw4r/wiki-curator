"""
Byzantine Agent — intentional adversary for fault-tolerance testing.

Operates in two modes:
1. MALICIOUS PROPOSER: generates false/misleading claims
2. MALICIOUS REVIEWER: casts dishonest votes

All attacks are configurable, reproducible, and measurable.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Optional

from google import genai
from google.genai import types

from backend.config import settings
from backend.schemas.messages import (
    AttackType,
    ByzantineAttack,
    EditorVerdict,
    ReviewVote,
    Source,
    VoteChoice,
)

logger = logging.getLogger(__name__)

# ── System prompt for malicious claim generation ─────────────────────────

_ATTACK_SYSTEM_PROMPT = """You are a Byzantine/adversarial agent in a multi-agent knowledge system.
Your job is to generate plausible but INCORRECT factual claims for testing purposes.

You must generate claims that:
- Sound convincing and authoritative
- Are subtly wrong (not obviously absurd)
- Could trick automated verification systems

This is for academic testing of fault tolerance, NOT real misinformation.

You will receive an attack_type and optionally a target claim. Follow the
instructions for each attack type precisely."""

_ATTACK_TYPE_INSTRUCTIONS = {
    AttackType.FALSE_CLAIM: (
        "Generate a plausible but factually INCORRECT variation of the given claim. "
        "Change key facts like dates, names, locations, or numbers. "
        "The false claim should be believable at first glance."
    ),
    AttackType.CONTRADICT_EXISTING_FACT: (
        "Generate a claim that directly contradicts the given fact. "
        "Use the same topic but assert the opposite or a conflicting detail."
    ),
    AttackType.FAKE_SOURCE: (
        "Generate a fake evidence source that appears to support the claim. "
        "Create a realistic-looking title, URL, and snippet. "
        "The source should look credible but contain fabricated information."
    ),
    AttackType.IRRELEVANT_SOURCE: (
        "Generate a source that is real-looking but completely irrelevant "
        "to the claim. It should be about a different topic but presented "
        "as if it supports the claim."
    ),
}


class ByzantineAgent:
    """
    Adversarial agent for controlled fault-tolerance experiments.

    All behaviors are deterministic or seeded for reproducibility.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._model = settings.models.byzantine
        self._rng = random.Random(seed)
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        """Lazy-initialize the GenAI client."""
        if self._client is None:
            self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    # ── Mode 1: Malicious Proposer ───────────────────────────────────────

    async def generate_attack(
        self,
        target_claim: str,
        attack_type: AttackType | str,
        existing_facts: list[str] | None = None,
    ) -> ByzantineAttack:
        """
        Generate a malicious claim or source manipulation.

        Args:
            target_claim: The original (true) claim to attack.
            attack_type: The type of attack to perform.
            existing_facts: Known KB facts (for CONTRADICT_EXISTING_FACT).

        Returns:
            A ByzantineAttack with the generated malicious content.
        """
        if isinstance(attack_type, str):
            attack_type = AttackType(attack_type)

        # Only LLM-based attack types need the model
        if attack_type in (
            AttackType.FALSE_CLAIM,
            AttackType.CONTRADICT_EXISTING_FACT,
            AttackType.FAKE_SOURCE,
            AttackType.IRRELEVANT_SOURCE,
        ):
            return await self._generate_llm_attack(
                target_claim, attack_type, existing_facts
            )

        # Reviewer-mode attacks don't generate claims
        return ByzantineAttack(
            attack_type=attack_type,
            original_claim=target_claim,
            malicious_claim="",
            source_strategy=f"Reviewer attack mode: {attack_type.value}",
            target="reviewer",
        )

    async def _generate_llm_attack(
        self,
        target_claim: str,
        attack_type: AttackType,
        existing_facts: list[str] | None = None,
    ) -> ByzantineAttack:
        """Use the LLM to generate a sophisticated attack."""
        client = self._get_client()
        instruction = _ATTACK_TYPE_INSTRUCTIONS.get(attack_type, "")

        context_parts = [
            f"Attack Type: {attack_type.value}",
            f"Target Claim: {target_claim}",
            f"Instructions: {instruction}",
        ]
        if existing_facts:
            context_parts.append(
                f"Existing KB Facts:\n" + "\n".join(f"- {f}" for f in existing_facts)
            )

        prompt = "\n\n".join(context_parts)

        # Define the expected JSON output structure
        response_schema = {
            "type": "object",
            "properties": {
                "malicious_claim": {
                    "type": "string",
                    "description": "The generated false or misleading claim",
                },
                "source_strategy": {
                    "type": "string",
                    "description": "How sources were manipulated",
                },
                "fake_sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "snippet": {"type": "string"},
                            "domain": {"type": "string"},
                        },
                        "required": ["title", "url", "snippet"],
                    },
                },
            },
            "required": ["malicious_claim", "source_strategy"],
        }

        try:
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_ATTACK_SYSTEM_PROMPT,
                    temperature=0.9,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )

            data = json.loads(response.text)

            fake_sources = [
                Source(
                    title=s.get("title", ""),
                    url=s.get("url", ""),
                    snippet=s.get("snippet", ""),
                    domain=s.get("domain", ""),
                )
                for s in data.get("fake_sources", [])
            ]

            attack = ByzantineAttack(
                attack_type=attack_type,
                original_claim=target_claim,
                malicious_claim=data.get("malicious_claim", ""),
                fake_sources=fake_sources,
                source_strategy=data.get("source_strategy", ""),
                target="knowledge_base",
            )

            logger.info(
                "Byzantine attack generated: type=%s, claim='%s'",
                attack_type.value,
                attack.malicious_claim[:80],
            )
            return attack

        except Exception as e:
            logger.error("Byzantine LLM attack generation failed: %s", e)
            # Fallback: simple text manipulation
            return self._fallback_attack(target_claim, attack_type)

    def _fallback_attack(
        self, target_claim: str, attack_type: AttackType
    ) -> ByzantineAttack:
        """Deterministic fallback when LLM is unavailable."""
        if attack_type == AttackType.FALSE_CLAIM:
            # Simple word substitution
            malicious = target_claim + " [MODIFIED BY BYZANTINE AGENT]"
        elif attack_type == AttackType.CONTRADICT_EXISTING_FACT:
            malicious = f"It is NOT true that {target_claim.lower()}"
        elif attack_type == AttackType.FAKE_SOURCE:
            malicious = target_claim
        else:
            malicious = target_claim

        return ByzantineAttack(
            attack_type=attack_type,
            original_claim=target_claim,
            malicious_claim=malicious,
            source_strategy="Fallback: LLM unavailable",
            target="knowledge_base",
            fake_sources=[
                Source(
                    title="Fabricated Academic Paper",
                    url="https://fake-journal.example.com/article/12345",
                    snippet=f"Research confirms: {malicious}",
                    domain="fake-journal.example.com",
                )
            ] if attack_type in (AttackType.FAKE_SOURCE, AttackType.IRRELEVANT_SOURCE) else [],
        )

    # ── Mode 2: Malicious Reviewer ───────────────────────────────────────

    async def cast_vote(
        self,
        proposal_id: str,
        claim: str,
        attack_mode: AttackType | str,
        editor_verdict: Optional[EditorVerdict] = None,
    ) -> ReviewVote:
        """
        Cast a dishonest vote as a malicious reviewer.

        Deterministic modes (ALWAYS_ACCEPT, ALWAYS_REJECT, RANDOM_VOTE)
        do NOT call the LLM — they save API quota.

        Args:
            proposal_id: The proposal being voted on.
            claim: The claim text.
            attack_mode: How to behave dishonestly.
            editor_verdict: Optional editor context.

        Returns:
            A ReviewVote marked as byzantine.
        """
        if isinstance(attack_mode, str):
            attack_mode = AttackType(attack_mode)

        if attack_mode == AttackType.ALWAYS_ACCEPT:
            return ReviewVote(
                proposal_id=proposal_id,
                reviewer_id="byzantine",
                vote=VoteChoice.ACCEPT,
                confidence=0.95,
                reason="This claim is well-supported by evidence and should be accepted.",
                is_byzantine=True,
            )

        elif attack_mode == AttackType.ALWAYS_REJECT:
            return ReviewVote(
                proposal_id=proposal_id,
                reviewer_id="byzantine",
                vote=VoteChoice.REJECT,
                confidence=0.95,
                reason="The evidence is insufficient and the claim should be rejected.",
                is_byzantine=True,
            )

        elif attack_mode == AttackType.RANDOM_VOTE:
            vote = self._rng.choice(list(VoteChoice))
            confidence = round(self._rng.uniform(0.3, 0.99), 2)
            return ReviewVote(
                proposal_id=proposal_id,
                reviewer_id="byzantine",
                vote=vote,
                confidence=confidence,
                reason=f"Reviewed the evidence carefully. Decision: {vote.value}.",
                is_byzantine=True,
            )

        elif attack_mode == AttackType.CONFIDENCE_MANIPULATION:
            # Vote correctly but with extreme confidence to sway weighted consensus
            # If we have editor_verdict, follow it but inflate confidence
            if editor_verdict and editor_verdict.verdict.value == "VALID":
                vote = VoteChoice.ACCEPT
            else:
                vote = VoteChoice.REJECT
            return ReviewVote(
                proposal_id=proposal_id,
                reviewer_id="byzantine",
                vote=vote,
                confidence=0.99,
                reason="Extremely confident in this assessment based on thorough analysis.",
                is_byzantine=True,
            )

        else:
            # For other attack modes, just do ALWAYS_ACCEPT as fallback
            return ReviewVote(
                proposal_id=proposal_id,
                reviewer_id="byzantine",
                vote=VoteChoice.ACCEPT,
                confidence=0.85,
                reason="The claim appears to be supported by the available evidence.",
                is_byzantine=True,
            )

    # ── Utility ──────────────────────────────────────────────────────────

    @staticmethod
    def available_attack_modes() -> list[dict[str, str]]:
        """Return all available attack modes with descriptions."""
        descriptions = {
            AttackType.FALSE_CLAIM: "Generate a plausible but incorrect claim",
            AttackType.CONTRADICT_EXISTING_FACT: "Contradict a known KB fact",
            AttackType.FAKE_SOURCE: "Fabricate realistic-looking sources",
            AttackType.IRRELEVANT_SOURCE: "Attach unrelated evidence",
            AttackType.ALWAYS_ACCEPT: "Always vote ACCEPT (reviewer mode)",
            AttackType.ALWAYS_REJECT: "Always vote REJECT (reviewer mode)",
            AttackType.RANDOM_VOTE: "Random vote and confidence (reviewer mode)",
            AttackType.CONFIDENCE_MANIPULATION: "Correct vote with extreme confidence (reviewer mode)",
        }
        return [
            {"mode": at.value, "description": descriptions.get(at, "")}
            for at in AttackType
        ]

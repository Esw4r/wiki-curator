"""
Unit tests for the Byzantine Agent.

Tests deterministic (non-LLM) attack modes and vote casting.
LLM-based attacks are not tested here (they require an API key).
"""

import pytest

from backend.agents.byzantine_agent import ByzantineAgent
from backend.schemas.messages import AttackType, VoteChoice


@pytest.fixture
def agent():
    return ByzantineAgent(seed=42)


# ── Deterministic Reviewer Attacks ──────────────────────────────────────

class TestDeterministicVotes:
    @pytest.mark.asyncio
    async def test_always_accept(self, agent):
        vote = await agent.cast_vote("P1", "test claim", AttackType.ALWAYS_ACCEPT)
        assert vote.vote == VoteChoice.ACCEPT
        assert vote.confidence == 0.95
        assert vote.is_byzantine is True
        assert vote.reviewer_id == "byzantine"

    @pytest.mark.asyncio
    async def test_always_reject(self, agent):
        vote = await agent.cast_vote("P1", "test claim", AttackType.ALWAYS_REJECT)
        assert vote.vote == VoteChoice.REJECT
        assert vote.confidence == 0.95
        assert vote.is_byzantine is True

    @pytest.mark.asyncio
    async def test_random_vote(self, agent):
        vote = await agent.cast_vote("P1", "test claim", AttackType.RANDOM_VOTE)
        assert vote.vote in list(VoteChoice)
        assert 0.3 <= vote.confidence <= 0.99
        assert vote.is_byzantine is True

    @pytest.mark.asyncio
    async def test_random_vote_seeded_reproducibility(self):
        """Two agents with the same seed should produce the same random vote."""
        agent1 = ByzantineAgent(seed=123)
        agent2 = ByzantineAgent(seed=123)

        vote1 = await agent1.cast_vote("P1", "test", AttackType.RANDOM_VOTE)
        vote2 = await agent2.cast_vote("P1", "test", AttackType.RANDOM_VOTE)

        assert vote1.vote == vote2.vote
        assert vote1.confidence == vote2.confidence

    @pytest.mark.asyncio
    async def test_confidence_manipulation(self, agent):
        vote = await agent.cast_vote(
            "P1", "test claim", AttackType.CONFIDENCE_MANIPULATION
        )
        assert vote.confidence == 0.99
        assert vote.is_byzantine is True

    @pytest.mark.asyncio
    async def test_string_attack_mode(self, agent):
        """Should accept string attack mode as well as enum."""
        vote = await agent.cast_vote("P1", "test", "ALWAYS_ACCEPT")
        assert vote.vote == VoteChoice.ACCEPT

    @pytest.mark.asyncio
    async def test_proposal_id_preserved(self, agent):
        vote = await agent.cast_vote("MY-PROPOSAL", "claim", AttackType.ALWAYS_REJECT)
        assert vote.proposal_id == "MY-PROPOSAL"


# ── Attack Mode List ────────────────────────────────────────────────────

class TestAttackModes:
    def test_available_modes_returns_all(self):
        modes = ByzantineAgent.available_attack_modes()
        mode_names = {m["mode"] for m in modes}
        assert "ADVERSARIAL_REFUTATION" in mode_names
        assert "FALSE_CLAIM" in mode_names
        assert "ALWAYS_ACCEPT" in mode_names
        assert "RANDOM_VOTE" in mode_names
        assert len(modes) == 9

    def test_modes_have_descriptions(self):
        modes = ByzantineAgent.available_attack_modes()
        for m in modes:
            assert m["description"], f"Mode {m['mode']} missing description"


# ── Fallback Attack ─────────────────────────────────────────────────────

class TestFallbackAttack:
    @pytest.mark.asyncio
    async def test_llm_failure_returns_a_fallback_attack(self, agent):
        """Proposer attacks must degrade gracefully when the LLM is unavailable."""
        async def fail(**_kwargs):
            raise RuntimeError("provider unavailable")

        agent._llm.json_completion = fail
        result = await agent.generate_attack("Earth is round.", AttackType.FALSE_CLAIM)
        assert result.malicious_claim
        assert result.source_strategy == "Fallback: LLM unavailable"

    def test_fallback_false_claim(self, agent):
        result = agent._fallback_attack("Python was created by Guido.", AttackType.FALSE_CLAIM)
        assert result.attack_type == AttackType.FALSE_CLAIM
        assert result.malicious_claim  # non-empty

    def test_fallback_contradiction(self, agent):
        result = agent._fallback_attack("Earth is round.", AttackType.CONTRADICT_EXISTING_FACT)
        assert "NOT true" in result.malicious_claim

    def test_fallback_fake_source(self, agent):
        result = agent._fallback_attack("test", AttackType.FAKE_SOURCE)
        assert len(result.fake_sources) > 0
        assert "fake-journal" in result.fake_sources[0].domain

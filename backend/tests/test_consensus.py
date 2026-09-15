"""
Unit tests for the Consensus Engine.
"""

import pytest

from backend.consensus.engine import ConsensusEngine
from backend.schemas.messages import (
    ConsensusMethod,
    ReviewVote,
    VoteChoice,
)


def _vote(proposal_id: str, reviewer_id: str, vote: VoteChoice, confidence: float = 0.8) -> ReviewVote:
    """Helper to create a ReviewVote quickly."""
    return ReviewVote(
        proposal_id=proposal_id,
        reviewer_id=reviewer_id,
        vote=vote,
        confidence=confidence,
        reason=f"Test vote: {vote.value}",
    )


@pytest.fixture
def engine():
    return ConsensusEngine()


# ── Majority Voting ─────────────────────────────────────────────────────

class TestMajorityVoting:
    def test_all_accept(self, engine):
        votes = [
            _vote("P1", "r1", VoteChoice.ACCEPT),
            _vote("P1", "r2", VoteChoice.ACCEPT),
            _vote("P1", "r3", VoteChoice.ACCEPT),
        ]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert result.decision == VoteChoice.ACCEPT
        assert result.accept_votes == 3
        assert result.reject_votes == 0

    def test_all_reject(self, engine):
        votes = [
            _vote("P1", "r1", VoteChoice.REJECT),
            _vote("P1", "r2", VoteChoice.REJECT),
            _vote("P1", "r3", VoteChoice.REJECT),
        ]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert result.decision == VoteChoice.REJECT
        assert result.reject_votes == 3

    def test_majority_accept(self, engine):
        votes = [
            _vote("P1", "r1", VoteChoice.ACCEPT),
            _vote("P1", "r2", VoteChoice.ACCEPT),
            _vote("P1", "r3", VoteChoice.REJECT),
        ]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert result.decision == VoteChoice.ACCEPT
        assert result.accept_votes == 2
        assert result.reject_votes == 1

    def test_majority_reject(self, engine):
        votes = [
            _vote("P1", "r1", VoteChoice.REJECT),
            _vote("P1", "r2", VoteChoice.REJECT),
            _vote("P1", "r3", VoteChoice.ACCEPT),
        ]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert result.decision == VoteChoice.REJECT

    def test_tie_accept_reject(self, engine):
        """When ACCEPT == REJECT, should fall back to NEEDS_MORE_EVIDENCE."""
        votes = [
            _vote("P1", "r1", VoteChoice.ACCEPT),
            _vote("P1", "r2", VoteChoice.REJECT),
        ]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert result.decision == VoteChoice.NEEDS_MORE_EVIDENCE

    def test_nme_dominates(self, engine):
        votes = [
            _vote("P1", "r1", VoteChoice.NEEDS_MORE_EVIDENCE),
            _vote("P1", "r2", VoteChoice.NEEDS_MORE_EVIDENCE),
            _vote("P1", "r3", VoteChoice.ACCEPT),
        ]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert result.decision == VoteChoice.NEEDS_MORE_EVIDENCE

    def test_no_votes(self, engine):
        result = engine.decide([], ConsensusMethod.MAJORITY)
        assert result.decision == VoteChoice.NEEDS_MORE_EVIDENCE

    def test_single_vote_accept(self, engine):
        votes = [_vote("P1", "r1", VoteChoice.ACCEPT)]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert result.decision == VoteChoice.ACCEPT

    def test_consensus_method_set(self, engine):
        votes = [_vote("P1", "r1", VoteChoice.ACCEPT)]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert result.consensus_method == ConsensusMethod.MAJORITY

    def test_vote_details_preserved(self, engine):
        votes = [
            _vote("P1", "r1", VoteChoice.ACCEPT, 0.9),
            _vote("P1", "r2", VoteChoice.REJECT, 0.7),
        ]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert len(result.vote_details) == 2

    def test_total_votes_counted(self, engine):
        votes = [
            _vote("P1", "r1", VoteChoice.ACCEPT),
            _vote("P1", "r2", VoteChoice.ACCEPT),
            _vote("P1", "r3", VoteChoice.REJECT),
        ]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert result.total_votes == 3


# ── Weighted Voting ─────────────────────────────────────────────────────

class TestWeightedVoting:
    def test_weighted_high_rep_wins(self, engine):
        """High-reputation REJECT should outweigh low-reputation ACCEPT."""
        votes = [
            _vote("P1", "r1", VoteChoice.ACCEPT, 0.8),
            _vote("P1", "r2", VoteChoice.REJECT, 0.9),
        ]
        reputations = {"r1": 0.3, "r2": 0.95}
        result = engine.decide(votes, ConsensusMethod.WEIGHTED, reputations)
        # r1 weight: 0.3 * 0.8 = 0.24 (ACCEPT)
        # r2 weight: 0.95 * 0.9 = 0.855 (REJECT)
        assert result.decision == VoteChoice.REJECT

    def test_weighted_quantity_over_quality(self, engine):
        """Multiple low-rep votes can outweigh one high-rep vote."""
        votes = [
            _vote("P1", "r1", VoteChoice.ACCEPT, 0.8),
            _vote("P1", "r2", VoteChoice.ACCEPT, 0.8),
            _vote("P1", "r3", VoteChoice.REJECT, 0.8),
        ]
        reputations = {"r1": 0.5, "r2": 0.5, "r3": 0.9}
        result = engine.decide(votes, ConsensusMethod.WEIGHTED, reputations)
        # ACCEPT weight: 0.5*0.8 + 0.5*0.8 = 0.8
        # REJECT weight: 0.9*0.8 = 0.72
        assert result.decision == VoteChoice.ACCEPT

    def test_weighted_method_set(self, engine):
        votes = [_vote("P1", "r1", VoteChoice.ACCEPT, 0.8)]
        reputations = {"r1": 0.75}
        result = engine.decide(votes, ConsensusMethod.WEIGHTED, reputations)
        assert result.consensus_method == ConsensusMethod.WEIGHTED

    def test_weighted_no_votes(self, engine):
        result = engine.decide([], ConsensusMethod.WEIGHTED, {"r1": 0.5})
        assert result.decision == VoteChoice.NEEDS_MORE_EVIDENCE

    def test_weighted_falls_back_to_majority_without_reputations(self, engine):
        """If method is WEIGHTED but no reputations provided, falls back to majority."""
        votes = [
            _vote("P1", "r1", VoteChoice.ACCEPT),
            _vote("P1", "r2", VoteChoice.ACCEPT),
            _vote("P1", "r3", VoteChoice.REJECT),
        ]
        result = engine.decide(votes, ConsensusMethod.WEIGHTED, None)
        # Should fall back to majority
        assert result.consensus_method == ConsensusMethod.MAJORITY
        assert result.decision == VoteChoice.ACCEPT


# ── String method dispatch ──────────────────────────────────────────────

class TestStringMethodDispatch:
    def test_string_majority(self, engine):
        votes = [_vote("P1", "r1", VoteChoice.ACCEPT)]
        result = engine.decide(votes, "majority")
        assert result.decision == VoteChoice.ACCEPT

    def test_string_weighted(self, engine):
        votes = [_vote("P1", "r1", VoteChoice.ACCEPT, 0.8)]
        result = engine.decide(votes, "weighted", {"r1": 0.9})
        assert result.decision == VoteChoice.ACCEPT


# ── Byzantine resilience scenarios ──────────────────────────────────────

class TestByzantineResilience:
    def test_one_byzantine_cannot_override_majority(self, engine):
        """2 honest ACCEPT vs 1 byzantine REJECT → ACCEPT wins."""
        votes = [
            _vote("P1", "r1", VoteChoice.ACCEPT),
            _vote("P1", "r2", VoteChoice.ACCEPT),
            ReviewVote(
                proposal_id="P1", reviewer_id="byz",
                vote=VoteChoice.REJECT, confidence=0.99,
                reason="Malicious", is_byzantine=True,
            ),
        ]
        result = engine.decide(votes, ConsensusMethod.MAJORITY)
        assert result.decision == VoteChoice.ACCEPT

    def test_weighted_limits_low_rep_byzantine(self, engine):
        """Byzantine agent with low reputation should have less influence."""
        votes = [
            _vote("P1", "r1", VoteChoice.ACCEPT, 0.8),
            ReviewVote(
                proposal_id="P1", reviewer_id="byz",
                vote=VoteChoice.REJECT, confidence=0.99,
                reason="Malicious", is_byzantine=True,
            ),
        ]
        reputations = {"r1": 0.95, "byz": 0.1}
        result = engine.decide(votes, ConsensusMethod.WEIGHTED, reputations)
        # r1: 0.95 * 0.8 = 0.76 (ACCEPT)
        # byz: 0.1 * 0.99 = 0.099 (REJECT)
        assert result.decision == VoteChoice.ACCEPT

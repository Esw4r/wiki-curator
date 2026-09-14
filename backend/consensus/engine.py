"""
Consensus Engine — deterministic vote aggregation.

This module is deliberately NOT an LLM. It receives reviewer votes
and computes a final group decision using configurable algorithms.
"""

from __future__ import annotations

import logging
from collections import Counter

from backend.config import settings
from backend.schemas.messages import (
    ConsensusDecision,
    ConsensusMethod,
    ReviewVote,
    VoteChoice,
)

logger = logging.getLogger(__name__)


class ConsensusEngine:
    """
    Aggregates reviewer votes into a single consensus decision.

    Supports:
    - Simple majority voting
    - Reputation-weighted voting
    """

    def decide(
        self,
        votes: list[ReviewVote],
        method: ConsensusMethod | str = ConsensusMethod.MAJORITY,
        reputations: dict[str, float] | None = None,
    ) -> ConsensusDecision:
        """
        Dispatcher — compute consensus using the selected algorithm.

        Args:
            votes: List of reviewer votes.
            method: "majority" or "weighted".
            reputations: Mapping of reviewer_id → reputation score (for weighted).

        Returns:
            A ConsensusDecision with the aggregated result.
        """
        if isinstance(method, str):
            method = ConsensusMethod(method)

        if method == ConsensusMethod.WEIGHTED and reputations:
            return self._compute_weighted(votes, reputations)
        return self._compute_majority(votes)

    def _compute_majority(self, votes: list[ReviewVote]) -> ConsensusDecision:
        """
        Simple majority voting.

        Rules:
        - ACCEPT if ACCEPT votes > REJECT votes
        - REJECT if REJECT votes > ACCEPT votes
        - NEEDS_MORE_EVIDENCE on tie or if NME dominates
        """
        if not votes:
            return ConsensusDecision(
                proposal_id="",
                decision=VoteChoice.NEEDS_MORE_EVIDENCE,
                reason="No votes received.",
            )

        proposal_id = votes[0].proposal_id
        counts = Counter(v.vote for v in votes)

        accept = counts.get(VoteChoice.ACCEPT, 0)
        reject = counts.get(VoteChoice.REJECT, 0)
        nme = counts.get(VoteChoice.NEEDS_MORE_EVIDENCE, 0)

        decision, reason = self._resolve_counts(accept, reject, nme)

        result = ConsensusDecision(
            proposal_id=proposal_id,
            decision=decision,
            accept_votes=accept,
            reject_votes=reject,
            needs_more_evidence_votes=nme,
            total_votes=len(votes),
            consensus_method=ConsensusMethod.MAJORITY,
            reason=reason,
            vote_details=votes,
        )

        logger.info(
            "Majority consensus for %s: %s (A=%d R=%d NME=%d)",
            proposal_id, decision.value, accept, reject, nme,
        )
        return result

    def _compute_weighted(
        self,
        votes: list[ReviewVote],
        reputations: dict[str, float],
    ) -> ConsensusDecision:
        """
        Reputation-weighted voting.

        Each vote is multiplied by the reviewer's reputation score.
        The category with the highest weighted sum wins.
        """
        if not votes:
            return ConsensusDecision(
                proposal_id="",
                decision=VoteChoice.NEEDS_MORE_EVIDENCE,
                consensus_method=ConsensusMethod.WEIGHTED,
                reason="No votes received.",
            )

        proposal_id = votes[0].proposal_id

        weighted_sums: dict[VoteChoice, float] = {
            VoteChoice.ACCEPT: 0.0,
            VoteChoice.REJECT: 0.0,
            VoteChoice.NEEDS_MORE_EVIDENCE: 0.0,
        }

        for v in votes:
            rep = reputations.get(v.reviewer_id, settings.reputation.initial_score)
            weighted_sums[v.vote] += rep * v.confidence

        # Count raw votes too for the record
        counts = Counter(v.vote for v in votes)
        accept_count = counts.get(VoteChoice.ACCEPT, 0)
        reject_count = counts.get(VoteChoice.REJECT, 0)
        nme_count = counts.get(VoteChoice.NEEDS_MORE_EVIDENCE, 0)

        # Find the winner
        max_weight = max(weighted_sums.values())
        winners = [k for k, v in weighted_sums.items() if v == max_weight]

        if len(winners) == 1:
            decision = winners[0]
            reason = (
                f"Weighted voting: ACCEPT={weighted_sums[VoteChoice.ACCEPT]:.2f}, "
                f"REJECT={weighted_sums[VoteChoice.REJECT]:.2f}, "
                f"NME={weighted_sums[VoteChoice.NEEDS_MORE_EVIDENCE]:.2f}. "
                f"Winner: {decision.value}"
            )
        else:
            # Tie → fall back to configured tie-break
            tie_break = settings.consensus.tie_break
            decision = VoteChoice(tie_break)
            reason = (
                f"Weighted voting tie between {[w.value for w in winners]}. "
                f"Tie-break applied: {tie_break}"
            )

        result = ConsensusDecision(
            proposal_id=proposal_id,
            decision=decision,
            accept_votes=accept_count,
            reject_votes=reject_count,
            needs_more_evidence_votes=nme_count,
            total_votes=len(votes),
            consensus_method=ConsensusMethod.WEIGHTED,
            reason=reason,
            vote_details=votes,
        )

        logger.info(
            "Weighted consensus for %s: %s (weights: A=%.2f R=%.2f NME=%.2f)",
            proposal_id, decision.value,
            weighted_sums[VoteChoice.ACCEPT],
            weighted_sums[VoteChoice.REJECT],
            weighted_sums[VoteChoice.NEEDS_MORE_EVIDENCE],
        )
        return result

    @staticmethod
    def _resolve_counts(
        accept: int, reject: int, nme: int
    ) -> tuple[VoteChoice, str]:
        """Determine winner from raw counts."""
        if accept > reject and accept > nme:
            return (
                VoteChoice.ACCEPT,
                f"Majority accepted ({accept} ACCEPT vs {reject} REJECT, {nme} NME).",
            )
        elif reject > accept and reject > nme:
            return (
                VoteChoice.REJECT,
                f"Majority rejected ({reject} REJECT vs {accept} ACCEPT, {nme} NME).",
            )
        elif nme > accept and nme > reject:
            return (
                VoteChoice.NEEDS_MORE_EVIDENCE,
                f"Majority needs more evidence ({nme} NME vs {accept} ACCEPT, {reject} REJECT).",
            )
        elif accept == reject:
            # Tie between accept and reject → NEEDS_MORE_EVIDENCE
            tie_break = settings.consensus.tie_break
            return (
                VoteChoice(tie_break),
                f"Tie between ACCEPT ({accept}) and REJECT ({reject}). "
                f"Tie-break: {tie_break}.",
            )
        elif accept == nme:
            return (
                VoteChoice.NEEDS_MORE_EVIDENCE,
                f"Tie between ACCEPT ({accept}) and NME ({nme}). "
                f"Defaulting to NEEDS_MORE_EVIDENCE.",
            )
        else:
            # reject == nme tie
            return (
                VoteChoice.REJECT,
                f"Tie between REJECT ({reject}) and NME ({nme}). "
                f"Defaulting to REJECT.",
            )

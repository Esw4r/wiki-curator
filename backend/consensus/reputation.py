"""
Reputation System — tracks and updates agent trust scores.

Reputation is used by the weighted consensus algorithm to give
more influence to historically reliable reviewers.
"""

from __future__ import annotations

import logging

from backend.config import settings
from backend.database import models as db
from backend.schemas.messages import VoteChoice

logger = logging.getLogger(__name__)


class ReputationManager:
    """
    Manages per-agent reputation scores.

    Scores are clamped to [min_score, max_score] from config.
    """

    async def get_reputation(self, agent_id: str) -> float:
        """Get the current reputation score for an agent."""
        agent = await db.get_agent(agent_id)
        if agent:
            return float(agent["reputation"])
        return settings.reputation.initial_score

    async def get_all_reputations(self) -> dict[str, float]:
        """Get reputation scores for all agents."""
        agents = await db.list_agents()
        return {a["id"]: float(a["reputation"]) for a in agents}

    async def update_after_decision(
        self,
        agent_id: str,
        agent_vote: VoteChoice,
        ground_truth: VoteChoice,
        is_byzantine_detected: bool = False,
    ) -> float:
        """
        Update an agent's reputation based on how their vote compared
        to the ground-truth decision.

        Args:
            agent_id: The agent whose reputation to update.
            agent_vote: What the agent voted.
            ground_truth: The correct decision (from experiments / oracle).
            is_byzantine_detected: Whether this agent was flagged as malicious.

        Returns:
            The new reputation score.
        """
        old_score = await self.get_reputation(agent_id)

        if is_byzantine_detected:
            delta = settings.reputation.malicious_detected_delta
            reason = "Byzantine behavior detected"
        elif agent_vote == ground_truth:
            delta = settings.reputation.correct_decision_delta
            reason = f"Correct vote ({agent_vote.value})"
        else:
            delta = settings.reputation.incorrect_decision_delta
            reason = f"Incorrect vote ({agent_vote.value} vs ground truth {ground_truth.value})"

        # Apply delta and clamp
        new_score = self._clamp(old_score + delta)

        # Persist
        await db.update_agent_reputation(agent_id, new_score)
        await db.insert_reputation_history(agent_id, old_score, new_score, reason)

        logger.info(
            "Reputation update for %s: %.2f → %.2f (%s)",
            agent_id, old_score, new_score, reason,
        )
        return new_score

    async def reset_all(self) -> None:
        """Reset all agent reputations to the initial score. Used for experiments."""
        agents = await db.list_agents()
        initial = settings.reputation.initial_score
        for agent in agents:
            old = float(agent["reputation"])
            await db.update_agent_reputation(agent["id"], initial)
            await db.insert_reputation_history(
                agent["id"], old, initial, "Reset for experiment"
            )
        logger.info("All reputations reset to %.2f", initial)

    async def get_history(
        self, agent_id: str, limit: int = 100
    ) -> list[dict]:
        """Get reputation history for an agent."""
        return await db.get_reputation_history(agent_id, limit)

    @staticmethod
    def _clamp(value: float) -> float:
        """Clamp reputation to configured bounds."""
        return max(
            settings.reputation.min_score,
            min(settings.reputation.max_score, value),
        )

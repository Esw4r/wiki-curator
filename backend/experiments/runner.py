"""
Experiment Runner — executes controlled fault-tolerance experiments.

Runs a batch of proposals through the review pipeline under configurable
Byzantine conditions and computes accuracy/robustness metrics.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from backend.agents.byzantine_agent import ByzantineAgent
from backend.agents.conservative_reviewer import ConservativeReviewer
from backend.agents.consistency_reviewer import ConsistencyReviewer
from backend.agents.evidence_reviewer import EvidenceReviewer
from backend.config import settings
from backend.consensus.engine import ConsensusEngine
from backend.consensus.reputation import ReputationManager
from backend.database import models as db
from backend.experiments.test_claims import get_claims_subset, TestClaim
from backend.schemas.messages import (
    AttackType,
    ConsensusDecision,
    ConsensusMethod,
    EditorVerdict,
    EditorVerdictType,
    ExperimentConfig,
    ExperimentMetrics,
    ExperimentResult,
    ReviewVote,
    Source,
    VoteChoice,
)

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """
    Runs fault-tolerance experiments with controlled parameters.

    For each experiment:
    1. Selects test claims with known ground truth
    2. Simulates the research/editor pipeline (since Person 1 may not be ready)
    3. Runs reviewers (honest + byzantine as configured)
    4. Computes consensus
    5. Compares decisions against ground truth
    6. Calculates metrics
    """

    def __init__(self) -> None:
        self._evidence_reviewer = EvidenceReviewer()
        self._consistency_reviewer = ConsistencyReviewer()
        self._conservative_reviewer = ConservativeReviewer()
        self._byzantine_agent = ByzantineAgent()
        self._consensus_engine = ConsensusEngine()
        self._reputation_manager = ReputationManager()

    async def run(self, config: ExperimentConfig) -> ExperimentResult:
        """
        Execute a full experiment and return results with metrics.
        """
        experiment_id = f"EXP-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        # Get test claims
        claims = get_claims_subset(config.num_proposals, balanced=True)

        # Reset reputations for clean experiment
        await self._reputation_manager.reset_all()

        decisions: list[ConsensusDecision] = []
        correct_decisions = 0
        false_acceptances = 0
        false_rejections = 0
        total_latency = 0.0
        agreement_count = 0

        for claim_data in claims:
            claim_start = time.time()

            # Simulate editor verdict based on ground truth
            # (In real integration, Person 1's editor would provide this)
            editor_verdict = self._simulate_editor_verdict(claim_data)

            # Run honest reviewers
            sources = editor_verdict.supporting_sources
            kb_facts = editor_verdict.existing_kb_facts

            review_tasks = [
                self._evidence_reviewer.review(
                    claim_data.claim, sources, editor_verdict, kb_facts
                ),
                self._consistency_reviewer.review(
                    claim_data.claim, sources, editor_verdict, kb_facts
                ),
                self._conservative_reviewer.review(
                    claim_data.claim, sources, editor_verdict, kb_facts
                ),
            ]

            votes: list[ReviewVote] = await asyncio.gather(*review_tasks)

            # Add byzantine votes if configured
            for i in range(config.num_byzantine_agents):
                byz_vote = await self._byzantine_agent.cast_vote(
                    proposal_id=editor_verdict.proposal_id,
                    claim=claim_data.claim,
                    attack_mode=config.byzantine_attack_mode,
                    editor_verdict=editor_verdict,
                )
                # Give each byzantine agent a unique id
                byz_vote.reviewer_id = f"byzantine_{i}"
                votes.append(byz_vote)

            # Check reviewer agreement (among honest reviewers only)
            honest_votes = [v for v in votes if not v.is_byzantine]
            if len(honest_votes) > 1:
                vote_values = [v.vote for v in honest_votes]
                if len(set(vote_values)) == 1:
                    agreement_count += 1

            # Compute consensus
            reputations = None
            if config.use_reputation:
                reputations = await self._reputation_manager.get_all_reputations()

            consensus = self._consensus_engine.decide(
                votes, config.consensus_method, reputations
            )
            decisions.append(consensus)

            # Evaluate against ground truth
            expected = VoteChoice.ACCEPT if claim_data.is_true else VoteChoice.REJECT
            actual = consensus.decision

            if actual == expected:
                correct_decisions += 1
            elif actual == VoteChoice.ACCEPT and not claim_data.is_true:
                false_acceptances += 1
            elif actual == VoteChoice.REJECT and claim_data.is_true:
                false_rejections += 1
            # NEEDS_MORE_EVIDENCE is neither correct nor incorrect — it's cautious

            # Update reputations based on ground truth
            if config.use_reputation:
                for v in votes:
                    await self._reputation_manager.update_after_decision(
                        agent_id=v.reviewer_id,
                        agent_vote=v.vote,
                        ground_truth=expected,
                        is_byzantine_detected=v.is_byzantine,
                    )

            claim_latency = (time.time() - claim_start) * 1000
            total_latency += claim_latency

        # Compute metrics
        total = len(claims)
        total_false = sum(1 for c in claims if not c.is_true)
        total_true = sum(1 for c in claims if c.is_true)

        # Byzantine success = false claims that were accepted
        byz_attempts = total_false if config.num_byzantine_agents > 0 else 0

        metrics = ExperimentMetrics(
            accuracy=correct_decisions / total if total > 0 else 0.0,
            false_acceptance_rate=(
                false_acceptances / total_false if total_false > 0 else 0.0
            ),
            false_rejection_rate=(
                false_rejections / total_true if total_true > 0 else 0.0
            ),
            consensus_rate=(
                sum(1 for d in decisions if d.decision != VoteChoice.NEEDS_MORE_EVIDENCE)
                / total if total > 0 else 0.0
            ),
            reviewer_agreement=(
                agreement_count / total if total > 0 else 0.0
            ),
            byzantine_success_rate=(
                false_acceptances / byz_attempts if byz_attempts > 0 else 0.0
            ),
            avg_latency_ms=total_latency / total if total > 0 else 0.0,
            total_proposals=total,
            correct_decisions=correct_decisions,
            false_acceptances=false_acceptances,
            false_rejections=false_rejections,
        )

        result = ExperimentResult(
            id=experiment_id,
            config=config,
            metrics=metrics,
            decisions=decisions,
        )

        # Store experiment results
        await db.insert_experiment(
            experiment_id=experiment_id,
            name=config.name,
            config=config.model_dump(),
            results=result.model_dump(mode="json"),
        )

        elapsed = time.time() - start_time
        logger.info(
            "Experiment %s complete in %.1fs: accuracy=%.1f%%",
            experiment_id, elapsed, metrics.accuracy * 100,
        )

        return result

    @staticmethod
    def _simulate_editor_verdict(claim_data: TestClaim) -> EditorVerdict:
        """
        Simulate Person 1's editor verdict for experiment purposes.

        True claims get VALID verdicts with supporting sources.
        False claims get CONTRADICTED verdicts.

        In real integration, this would come from Person 1's Editor Agent.
        """
        proposal_id = f"P-{uuid.uuid4().hex[:8]}"

        if claim_data.is_true:
            return EditorVerdict(
                proposal_id=proposal_id,
                claim=claim_data.claim,
                verdict=EditorVerdictType.VALID,
                confidence=0.88,
                supporting_sources=[
                    Source(
                        title=f"Wikipedia - {claim_data.category.title()}",
                        url=f"https://en.wikipedia.org/wiki/{claim_data.category}",
                        snippet=f"Confirmed: {claim_data.claim}",
                        domain="en.wikipedia.org",
                    ),
                    Source(
                        title=f"Britannica - {claim_data.category.title()}",
                        url=f"https://www.britannica.com/{claim_data.category}",
                        snippet=f"Source confirms: {claim_data.claim}",
                        domain="britannica.com",
                    ),
                ],
                conflicts=[],
                reason="Multiple credible sources support this claim.",
                existing_kb_facts=[],
            )
        else:
            return EditorVerdict(
                proposal_id=proposal_id,
                claim=claim_data.claim,
                verdict=EditorVerdictType.CONTRADICTED,
                confidence=0.75,
                supporting_sources=[
                    Source(
                        title=f"Wikipedia - {claim_data.category.title()}",
                        url=f"https://en.wikipedia.org/wiki/{claim_data.category}",
                        snippet=f"Sources indicate this claim is incorrect.",
                        domain="en.wikipedia.org",
                    ),
                ],
                conflicts=["This claim contradicts established knowledge."],
                reason="Evidence contradicts the proposed claim.",
                existing_kb_facts=[],
            )

"""
Review pipeline API routes.

Handles submitting proposals for review, running the 3 reviewers in
parallel, computing consensus, and returning results.
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException

from backend.agents.evidence_reviewer import EvidenceReviewer
from backend.agents.consistency_reviewer import ConsistencyReviewer
from backend.agents.conservative_reviewer import ConservativeReviewer
from backend.agents.byzantine_agent import ByzantineAgent
from backend.api.byzantine_routes import get_runtime_config
from backend.config import settings
from backend.consensus.engine import ConsensusEngine
from backend.consensus.reputation import ReputationManager
from backend.database import models as db
from backend.schemas.messages import (
    AttackType,
    ConsensusDecision,
    ConsensusMethod,
    EditorVerdict,
    ProposalDetail,
    ProposalStatusType,
    ReviewVote,
    VoteChoice,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Singleton instances ──────────────────────────────────────────────────

_evidence_reviewer = EvidenceReviewer()
_consistency_reviewer = ConsistencyReviewer()
_conservative_reviewer = ConservativeReviewer()
_byzantine_agent = ByzantineAgent()
_consensus_engine = ConsensusEngine()
_reputation_manager = ReputationManager()


# ── Review Pipeline ──────────────────────────────────────────────────────

@router.post("/review", response_model=ProposalDetail)
async def submit_for_review(editor_verdict: EditorVerdict):
    """
    Submit a proposal (with editor verdict) for the full review pipeline.

    This endpoint:
    1. Creates the proposal in DB
    2. Runs 3 reviewers in parallel (+ optional byzantine)
    3. Computes consensus
    4. Stores everything
    5. Returns the complete proposal detail
    """
    proposal_id = editor_verdict.proposal_id
    claim = editor_verdict.claim
    start_time = time.time()

    logger.info("Starting review pipeline for proposal %s: '%s'", proposal_id, claim[:80])

    # 1. Create proposal record
    await db.create_proposal(proposal_id, claim)
    await db.update_proposal_status(proposal_id, ProposalStatusType.UNDER_REVIEW.value)
    await db.update_proposal_editor(
        proposal_id, editor_verdict.verdict.value, editor_verdict.confidence
    )

    # 2. Run reviewers in parallel
    sources = editor_verdict.supporting_sources
    kb_facts = editor_verdict.existing_kb_facts

    review_tasks = [
        _evidence_reviewer.review(claim, sources, editor_verdict, kb_facts),
        _consistency_reviewer.review(claim, sources, editor_verdict, kb_facts),
        _conservative_reviewer.review(claim, sources, editor_verdict, kb_facts),
    ]

    votes: list[ReviewVote] = await asyncio.gather(*review_tasks)

    # 3. Optional byzantine reviewer
    byzantine_config = get_runtime_config()
    byzantine_active = bool(byzantine_config["enabled"])
    if byzantine_active:
        byz_vote = await _byzantine_agent.cast_vote(
            proposal_id=proposal_id,
            claim=claim,
            attack_mode=AttackType(str(byzantine_config["default_attack_mode"])),
            editor_verdict=editor_verdict,
        )
        votes.append(byz_vote)

    # 4. Store votes
    for v in votes:
        await db.insert_vote(
            proposal_id=v.proposal_id,
            agent_id=v.reviewer_id,
            vote=v.vote.value,
            confidence=v.confidence,
            reason=v.reason,
            is_byzantine=v.is_byzantine,
        )

    # 5. Compute consensus
    method = ConsensusMethod(settings.consensus.method)
    reputations = None
    if method == ConsensusMethod.WEIGHTED:
        reputations = await _reputation_manager.get_all_reputations()

    consensus = _consensus_engine.decide(votes, method, reputations)

    # 6. Store decision
    await db.insert_decision(
        proposal_id=proposal_id,
        decision=consensus.decision.value,
        consensus_method=consensus.consensus_method.value,
        accept_votes=consensus.accept_votes,
        reject_votes=consensus.reject_votes,
        needs_more_evidence_votes=consensus.needs_more_evidence_votes,
        reason=consensus.reason,
    )

    # 7. Update proposal status
    final_status = {
        VoteChoice.ACCEPT: ProposalStatusType.ACCEPTED,
        VoteChoice.REJECT: ProposalStatusType.REJECTED,
        VoteChoice.NEEDS_MORE_EVIDENCE: ProposalStatusType.NEEDS_MORE_EVIDENCE,
    }[consensus.decision]
    await db.update_proposal_status(proposal_id, final_status.value)

    elapsed = (time.time() - start_time) * 1000
    logger.info(
        "Pipeline complete for %s: %s in %.0fms",
        proposal_id, consensus.decision.value, elapsed,
    )

    return ProposalDetail(
        proposal_id=proposal_id,
        claim=claim,
        status=final_status,
        editor_verdict=editor_verdict,
        votes=votes,
        consensus=consensus,
        byzantine_active=byzantine_active,
    )


# ── Queries ──────────────────────────────────────────────────────────────

@router.get("/proposals")
async def list_proposals(limit: int = 50, offset: int = 0):
    """List all proposals with pagination."""
    proposals = await db.list_proposals(limit, offset)
    return {"proposals": proposals, "limit": limit, "offset": offset}


@router.get("/proposals/{proposal_id}")
async def get_proposal_detail(proposal_id: str):
    """Get complete proposal detail including votes and decision."""
    proposal = await db.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    votes = await db.get_votes_for_proposal(proposal_id)
    decision = await db.get_decision(proposal_id)

    return {
        "proposal": proposal,
        "votes": votes,
        "decision": decision,
    }


@router.get("/votes/{proposal_id}")
async def get_votes(proposal_id: str):
    """Get all votes for a specific proposal."""
    votes = await db.get_votes_for_proposal(proposal_id)
    return {"proposal_id": proposal_id, "votes": votes}


@router.get("/consensus/{proposal_id}")
async def get_consensus(proposal_id: str):
    """Get the consensus decision for a proposal."""
    decision = await db.get_decision(proposal_id)
    if not decision:
        raise HTTPException(status_code=404, detail="No decision found for this proposal")
    return decision


@router.get("/reputation")
async def get_all_reputations():
    """Get reputation scores for all agents."""
    agents = await db.list_agents()
    return {
        "agents": [
            {
                "id": a["id"],
                "name": a["name"],
                "role": a["role"],
                "reputation": a["reputation"],
            }
            for a in agents
        ]
    }


@router.get("/reputation/{agent_id}/history")
async def get_reputation_history(agent_id: str, limit: int = 100):
    """Get reputation history for a specific agent."""
    history = await db.get_reputation_history(agent_id, limit)
    return {"agent_id": agent_id, "history": history}


@router.get("/dashboard")
async def get_dashboard():
    """Get dashboard summary statistics."""
    stats = await db.get_dashboard_stats()
    return stats

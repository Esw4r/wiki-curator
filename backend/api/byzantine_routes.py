"""
Byzantine Agent control API routes.

Provides endpoints for generating attacks, casting malicious votes,
listing attack modes, and toggling the byzantine agent on/off.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.agents.byzantine_agent import ByzantineAgent
from backend.database import models as db
from backend.schemas.messages import (
    AttackType,
    ByzantineAttack,
    ByzantineVoteRequest,
    ReviewVote,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_byzantine_agent = ByzantineAgent()


# ── Request models ───────────────────────────────────────────────────────

class AttackRequest(BaseModel):
    """Request body for generating an attack."""
    target_claim: str = Field(description="The original true claim to attack")
    attack_type: AttackType = AttackType.FALSE_CLAIM
    existing_facts: list[str] = Field(default_factory=list)


class ByzantineConfigUpdate(BaseModel):
    """Request body for updating byzantine configuration."""
    enabled: bool | None = None
    default_attack_mode: AttackType | None = None
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)


# ── In-memory config state (mirrors yaml but can be toggled at runtime) ─

_runtime_config = {
    "enabled": False,
    "default_attack_mode": "FALSE_CLAIM",
    "intensity": 0.8,
}


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("/attack", response_model=ByzantineAttack)
async def generate_attack(request: AttackRequest):
    """
    Generate a malicious claim or source manipulation.

    Uses the LLM for claim-based attacks; deterministic for reviewer attacks.
    """
    logger.info(
        "Generating %s attack against: '%s'",
        request.attack_type.value,
        request.target_claim[:80],
    )
    attack = await _byzantine_agent.generate_attack(
        target_claim=request.target_claim,
        attack_type=request.attack_type,
        existing_facts=request.existing_facts if request.existing_facts else None,
    )
    return attack


@router.post("/vote", response_model=ReviewVote)
async def cast_byzantine_vote(request: ByzantineVoteRequest):
    """
    Cast a malicious vote as the Byzantine reviewer.

    The vote is stored in the DB and marked as byzantine.
    """
    vote = await _byzantine_agent.cast_vote(
        proposal_id=request.proposal_id,
        claim=request.claim,
        attack_mode=request.attack_mode,
        editor_verdict=request.editor_verdict,
    )

    # Store the vote
    await db.insert_vote(
        proposal_id=vote.proposal_id,
        agent_id=vote.reviewer_id,
        vote=vote.vote.value,
        confidence=vote.confidence,
        reason=vote.reason,
        is_byzantine=True,
    )

    logger.info(
        "Byzantine vote cast: %s (conf=%.2f) for proposal %s",
        vote.vote.value,
        vote.confidence,
        vote.proposal_id,
    )
    return vote


@router.get("/modes")
async def list_attack_modes():
    """List all available attack modes with descriptions."""
    return {"modes": ByzantineAgent.available_attack_modes()}


@router.get("/config")
async def get_byzantine_config():
    """Get current byzantine agent configuration."""
    return _runtime_config


@router.put("/config")
async def update_byzantine_config(update: ByzantineConfigUpdate):
    """Enable/disable the byzantine agent or change its attack mode."""
    if update.enabled is not None:
        _runtime_config["enabled"] = update.enabled
    if update.default_attack_mode is not None:
        _runtime_config["default_attack_mode"] = update.default_attack_mode.value
    if update.intensity is not None:
        _runtime_config["intensity"] = update.intensity

    logger.info("Byzantine config updated: %s", _runtime_config)
    return _runtime_config

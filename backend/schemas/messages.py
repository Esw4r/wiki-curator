"""
Shared Pydantic v2 message contracts for inter-agent communication.

These schemas define the boundary between Person 1 (Research/Editor) and
Person 2 (Reviewers/Consensus/Byzantine). Both sides import from here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────

class VoteChoice(str, Enum):
    """Possible reviewer votes."""
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"


class EditorVerdictType(str, Enum):
    """Editor's structured verdict on a claim."""
    VALID = "VALID"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ConsensusMethod(str, Enum):
    """Supported consensus algorithms."""
    MAJORITY = "majority"
    WEIGHTED = "weighted"


class AttackType(str, Enum):
    """Byzantine agent attack modes."""
    FALSE_CLAIM = "FALSE_CLAIM"
    CONTRADICT_EXISTING_FACT = "CONTRADICT_EXISTING_FACT"
    FAKE_SOURCE = "FAKE_SOURCE"
    IRRELEVANT_SOURCE = "IRRELEVANT_SOURCE"
    ALWAYS_ACCEPT = "ALWAYS_ACCEPT"
    ALWAYS_REJECT = "ALWAYS_REJECT"
    RANDOM_VOTE = "RANDOM_VOTE"
    CONFIDENCE_MANIPULATION = "CONFIDENCE_MANIPULATION"


class ProposalStatusType(str, Enum):
    """Lifecycle status of a proposal."""
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"


class AgentRole(str, Enum):
    """Roles an agent can have in the system."""
    REVIEWER = "REVIEWER"
    BYZANTINE = "BYZANTINE"
    RESEARCH = "RESEARCH"
    EDITOR = "EDITOR"


# ── Source & Research ────────────────────────────────────────────────────

class Source(BaseModel):
    """A single evidence source returned by the Research Agent."""
    title: str = Field(description="Title of the source page/document")
    url: str = Field(description="URL of the source")
    snippet: str = Field(description="Relevant text snippet from the source")
    domain: str = Field(default="", description="Domain of the source (e.g. wikipedia.org)")


class ResearchOutput(BaseModel):
    """Output from Person 1's Research Agent → input to Editor."""
    proposal_id: str = Field(default_factory=lambda: f"P-{uuid.uuid4().hex[:8]}")
    claim: str = Field(description="The factual claim being evaluated")
    sources: list[Source] = Field(default_factory=list, description="Evidence sources found")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Editor ───────────────────────────────────────────────────────────────

class EditorVerdict(BaseModel):
    """
    Output from Person 1's Editor Agent → input to Reviewers.
    This is the primary hand-off from Person 1 to Person 2.
    """
    proposal_id: str
    claim: str
    verdict: EditorVerdictType
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_sources: list[Source] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    reason: str = Field(default="")
    existing_kb_facts: list[str] = Field(
        default_factory=list,
        description="Previously accepted facts relevant to this claim"
    )


# ── Reviewer ─────────────────────────────────────────────────────────────

class ReviewVote(BaseModel):
    """A single reviewer's vote on a proposal."""
    proposal_id: str
    reviewer_id: str
    vote: VoteChoice
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(default="")
    is_byzantine: bool = Field(default=False, description="Whether this vote came from a byzantine agent")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Consensus ────────────────────────────────────────────────────────────

class ConsensusDecision(BaseModel):
    """Final aggregated decision from the Consensus Engine."""
    proposal_id: str
    decision: VoteChoice
    accept_votes: int = 0
    reject_votes: int = 0
    needs_more_evidence_votes: int = 0
    total_votes: int = 0
    consensus_method: ConsensusMethod = ConsensusMethod.MAJORITY
    reason: str = Field(default="")
    vote_details: list[ReviewVote] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Byzantine ────────────────────────────────────────────────────────────

class ByzantineAttack(BaseModel):
    """Output from the Byzantine Agent's attack generation."""
    attack_type: AttackType
    original_claim: str = Field(default="", description="The original true claim (if applicable)")
    malicious_claim: str = Field(default="", description="The generated malicious claim")
    fake_sources: list[Source] = Field(default_factory=list)
    source_strategy: str = Field(default="", description="How sources were manipulated")
    target: str = Field(default="knowledge_base", description="Target of the attack")


class ByzantineVoteRequest(BaseModel):
    """Request to have the Byzantine Agent cast a malicious vote."""
    proposal_id: str
    claim: str
    editor_verdict: Optional[EditorVerdict] = None
    attack_mode: AttackType = AttackType.ALWAYS_ACCEPT


# ── Reputation ───────────────────────────────────────────────────────────

class ReputationRecord(BaseModel):
    """A snapshot of an agent's reputation change."""
    agent_id: str
    old_score: float
    new_score: float
    reason: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentInfo(BaseModel):
    """Public info about an agent in the system."""
    id: str
    name: str
    role: AgentRole
    model: str = ""
    reputation: float = 0.75
    status: str = "active"


# ── Proposal Status (full pipeline view for UI) ─────────────────────────

class ProposalDetail(BaseModel):
    """Complete proposal state for the frontend."""
    proposal_id: str
    claim: str
    status: ProposalStatusType = ProposalStatusType.PENDING
    editor_verdict: Optional[EditorVerdict] = None
    votes: list[ReviewVote] = Field(default_factory=list)
    consensus: Optional[ConsensusDecision] = None
    byzantine_active: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Experiment ───────────────────────────────────────────────────────────

class ExperimentConfig(BaseModel):
    """Configuration for a fault-tolerance experiment run."""
    name: str = Field(default="Unnamed Experiment")
    num_byzantine_agents: int = Field(default=0, ge=0, le=3)
    byzantine_attack_mode: AttackType = AttackType.FALSE_CLAIM
    consensus_method: ConsensusMethod = ConsensusMethod.MAJORITY
    num_proposals: int = Field(default=10, ge=1, le=200)
    use_reputation: bool = False


class ExperimentMetrics(BaseModel):
    """Computed metrics from an experiment run."""
    accuracy: float = 0.0
    false_acceptance_rate: float = 0.0
    false_rejection_rate: float = 0.0
    consensus_rate: float = 0.0
    reviewer_agreement: float = 0.0
    byzantine_success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    total_proposals: int = 0
    correct_decisions: int = 0
    false_acceptances: int = 0
    false_rejections: int = 0


class ExperimentResult(BaseModel):
    """Full result of an experiment run."""
    id: str = Field(default_factory=lambda: f"EXP-{uuid.uuid4().hex[:8]}")
    config: ExperimentConfig
    metrics: ExperimentMetrics
    decisions: list[ConsensusDecision] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

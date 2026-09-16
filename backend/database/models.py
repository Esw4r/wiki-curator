"""
Database query helpers for Person 2's tables: proposals, votes, decisions,
agents, reputation_history, and experiment_runs.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import aiosqlite

from backend.database.db import get_db


# ── Proposals ────────────────────────────────────────────────────────────

async def create_proposal(
    proposal_id: str,
    claim: str,
    proposer_agent: str = "user",
) -> dict[str, Any]:
    """Insert a new proposal."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR IGNORE INTO proposals (id, claim, proposer_agent) VALUES (?, ?, ?)",
            (proposal_id, claim, proposer_agent),
        )
        await db.commit()
        return {"id": proposal_id, "claim": claim, "status": "PENDING"}
    finally:
        await db.close()


async def update_proposal_status(proposal_id: str, status: str) -> None:
    """Update a proposal's lifecycle status."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE proposals SET status = ? WHERE id = ?",
            (status, proposal_id),
        )
        await db.commit()
    finally:
        await db.close()


async def update_proposal_editor(
    proposal_id: str, verdict: str, confidence: float
) -> None:
    """Store the editor's verdict on a proposal."""
    db = await get_db()
    try:
        await db.execute(
            """UPDATE proposals
               SET editor_verdict = ?, editor_confidence = ?
               WHERE id = ?""",
            (verdict, confidence, proposal_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_proposal(proposal_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single proposal."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM proposals WHERE id = ?", (proposal_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_proposals(
    limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """List proposals with pagination."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM proposals ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Votes ────────────────────────────────────────────────────────────────

async def insert_vote(
    proposal_id: str,
    agent_id: str,
    vote: str,
    confidence: float,
    reason: str = "",
    is_byzantine: bool = False,
) -> int:
    """Insert a reviewer vote and return the new row id."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO votes
               (proposal_id, agent_id, vote, confidence, reason, is_byzantine)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (proposal_id, agent_id, vote, confidence, reason, int(is_byzantine)),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        await db.close()


async def get_votes_for_proposal(
    proposal_id: str,
) -> list[dict[str, Any]]:
    """Get all votes for a proposal."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM votes WHERE proposal_id = ? ORDER BY created_at",
            (proposal_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Decisions ────────────────────────────────────────────────────────────

async def insert_decision(
    proposal_id: str,
    decision: str,
    consensus_method: str,
    accept_votes: int,
    reject_votes: int,
    needs_more_evidence_votes: int,
    reason: str = "",
) -> None:
    """Insert a consensus decision."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO decisions
               (proposal_id, decision, consensus_method,
                accept_votes, reject_votes,
                needs_more_evidence_votes, reason)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                proposal_id, decision, consensus_method,
                accept_votes, reject_votes,
                needs_more_evidence_votes, reason,
            ),
        )
        await db.commit()
    finally:
        await db.close()


async def get_decision(proposal_id: str) -> Optional[dict[str, Any]]:
    """Get the consensus decision for a proposal."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM decisions WHERE proposal_id = ?", (proposal_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_decisions(
    limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """List all decisions."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Agents ───────────────────────────────────────────────────────────────

async def get_agent(agent_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single agent."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_agents() -> list[dict[str, Any]]:
    """List all agents."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM agents ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_agent_reputation(
    agent_id: str, new_reputation: float
) -> None:
    """Update an agent's reputation score."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE agents SET reputation = ? WHERE id = ?",
            (new_reputation, agent_id),
        )
        await db.commit()
    finally:
        await db.close()


# ── Reputation History ───────────────────────────────────────────────────

async def insert_reputation_history(
    agent_id: str,
    old_score: float,
    new_score: float,
    reason: str = "",
) -> None:
    """Record a reputation change."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO reputation_history
               (agent_id, old_score, new_score, reason)
               VALUES (?, ?, ?, ?)""",
            (agent_id, old_score, new_score, reason),
        )
        await db.commit()
    finally:
        await db.close()


async def get_reputation_history(
    agent_id: str, limit: int = 100
) -> list[dict[str, Any]]:
    """Get reputation history for an agent."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM reputation_history
               WHERE agent_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (agent_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Experiment Runs ──────────────────────────────────────────────────────

async def insert_experiment(
    experiment_id: str,
    name: str,
    config: dict[str, Any],
    results: dict[str, Any],
) -> None:
    """Store an experiment run."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO experiment_runs (id, name, config_json, results_json)
               VALUES (?, ?, ?, ?)""",
            (experiment_id, name, json.dumps(config), json.dumps(results)),
        )
        await db.commit()
    finally:
        await db.close()


async def get_experiment(experiment_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single experiment run."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM experiment_runs WHERE id = ?", (experiment_id,)
        )
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            result["config_json"] = json.loads(result.get("config_json", "{}"))
            result["results_json"] = json.loads(result.get("results_json", "{}"))
            return result
        return None
    finally:
        await db.close()


async def list_experiments(
    limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """List all experiment runs."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM experiment_runs
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            r = dict(row)
            r["config_json"] = json.loads(r.get("config_json", "{}"))
            r["results_json"] = json.loads(r.get("results_json", "{}"))
            results.append(r)
        return results
    finally:
        await db.close()


# ── Stats ────────────────────────────────────────────────────────────────

async def get_dashboard_stats() -> dict[str, Any]:
    """Get summary statistics for the dashboard."""
    db = await get_db()
    try:
        # Total proposals
        cursor = await db.execute("SELECT COUNT(*) as c FROM proposals")
        total_proposals = (await cursor.fetchone())["c"]

        # Decisions breakdown
        cursor = await db.execute(
            """SELECT decision, COUNT(*) as c
               FROM decisions GROUP BY decision"""
        )
        decision_counts = {row["decision"]: row["c"] for row in await cursor.fetchall()}

        # Total votes
        cursor = await db.execute("SELECT COUNT(*) as c FROM votes")
        total_votes = (await cursor.fetchone())["c"]

        # Byzantine votes
        cursor = await db.execute(
            "SELECT COUNT(*) as c FROM votes WHERE is_byzantine = 1"
        )
        byzantine_votes = (await cursor.fetchone())["c"]

        # Agent reputations
        cursor = await db.execute("SELECT id, name, reputation FROM agents")
        agents = [dict(r) for r in await cursor.fetchall()]

        accepted = decision_counts.get("ACCEPT", 0)
        total_decisions = sum(decision_counts.values()) if decision_counts else 0
        acceptance_rate = (accepted / total_decisions * 100) if total_decisions else 0

        return {
            "total_proposals": total_proposals,
            "total_decisions": total_decisions,
            "total_votes": total_votes,
            "byzantine_votes": byzantine_votes,
            "acceptance_rate": round(acceptance_rate, 1),
            "decision_counts": decision_counts,
            "agents": agents,
        }
    finally:
        await db.close()

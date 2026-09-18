"""
SQLite async connection manager and schema initialization.
"""

from __future__ import annotations

import aiosqlite

from backend.config import settings

# ── Schema SQL ───────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL,
    model       TEXT DEFAULT '',
    reputation  REAL DEFAULT 0.75,
    status      TEXT DEFAULT 'active',
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proposals (
    id              TEXT PRIMARY KEY,
    claim           TEXT NOT NULL,
    proposer_agent  TEXT DEFAULT 'user',
    status          TEXT DEFAULT 'PENDING',
    editor_verdict  TEXT DEFAULT NULL,
    editor_confidence REAL DEFAULT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS votes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL REFERENCES proposals(id),
    agent_id    TEXT NOT NULL REFERENCES agents(id),
    vote        TEXT NOT NULL,
    confidence  REAL DEFAULT 0.5,
    reason      TEXT DEFAULT '',
    is_byzantine INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decisions (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id                 TEXT UNIQUE NOT NULL REFERENCES proposals(id),
    decision                    TEXT NOT NULL,
    consensus_method            TEXT DEFAULT 'majority',
    accept_votes                INTEGER DEFAULT 0,
    reject_votes                INTEGER DEFAULT 0,
    needs_more_evidence_votes   INTEGER DEFAULT 0,
    reason                      TEXT DEFAULT '',
    created_at                  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reputation_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id    TEXT NOT NULL REFERENCES agents(id),
    old_score   REAL NOT NULL,
    new_score   REAL NOT NULL,
    reason      TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS experiment_runs (
    id          TEXT PRIMARY KEY,
    name        TEXT DEFAULT '',
    config_json TEXT DEFAULT '{}',
    results_json TEXT DEFAULT '{}',
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    fact_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'ACCEPTED',
    accepted_proposal_id TEXT UNIQUE REFERENCES proposals(id),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    domain TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proposal_evidence (
    proposal_id TEXT NOT NULL REFERENCES proposals(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    snippet TEXT NOT NULL,
    query TEXT DEFAULT '',
    rank INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (proposal_id, source_id)
);

CREATE TABLE IF NOT EXISTS fact_sources (
    fact_id TEXT NOT NULL REFERENCES facts(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (fact_id, source_id)
);

CREATE TABLE IF NOT EXISTS fact_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id TEXT NOT NULL REFERENCES facts(id),
    proposal_id TEXT REFERENCES proposals(id),
    action TEXT NOT NULL,
    reason TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_proposal_evidence_proposal ON proposal_evidence(proposal_id);
CREATE INDEX IF NOT EXISTS idx_facts_status ON facts(status);
"""

# ── Default agents to seed ───────────────────────────────────────────────

_SEED_AGENTS = [
    ("reviewer_1", "Evidence Reviewer", "REVIEWER", "openai/gpt-oss-20b", 0.75),
    ("reviewer_2", "Consistency Reviewer", "REVIEWER", "openai/gpt-oss-20b", 0.75),
    ("reviewer_3", "Conservative Reviewer", "REVIEWER", "openai/gpt-oss-20b", 0.75),
    ("byzantine", "Byzantine Agent", "BYZANTINE", "openai/gpt-oss-20b", 0.50),
]


async def get_db() -> aiosqlite.Connection:
    """Get an async SQLite connection."""
    db = await aiosqlite.connect(settings.database.path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA foreign_keys=ON;")
    return db


async def init_db() -> None:
    """Create tables and seed default agents."""
    db = await get_db()
    try:
        await db.executescript(_SCHEMA_SQL)

        # Seed agents if they don't exist
        for agent_id, name, role, model, rep in _SEED_AGENTS:
            await db.execute(
                """
                INSERT OR IGNORE INTO agents (id, name, role, model, reputation)
                VALUES (?, ?, ?, ?, ?)
                """,
                (agent_id, name, role, model, rep),
            )
            await db.execute("UPDATE agents SET model = ? WHERE id = ?", (model, agent_id))
        await db.commit()
    finally:
        await db.close()


async def close_db(db: aiosqlite.Connection) -> None:
    """Close an async SQLite connection."""
    await db.close()

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
"""

# ── Default agents to seed ───────────────────────────────────────────────

_SEED_AGENTS = [
    ("reviewer_1", "Evidence Reviewer", "REVIEWER", "gemini-2.5-flash", 0.75),
    ("reviewer_2", "Consistency Reviewer", "REVIEWER", "gemini-2.5-flash", 0.75),
    ("reviewer_3", "Conservative Reviewer", "REVIEWER", "gemini-2.5-flash-lite", 0.75),
    ("byzantine", "Byzantine Agent", "BYZANTINE", "gemini-2.5-flash-lite", 0.50),
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
        await db.commit()
    finally:
        await db.close()


async def close_db(db: aiosqlite.Connection) -> None:
    """Close an async SQLite connection."""
    await db.close()

"""Knowledge-base persistence layered on the shared SQLite database."""

from __future__ import annotations

import re
import uuid
from typing import Any

from backend.database.db import get_db
from backend.schemas.messages import Source


def normalize_fact(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold()).rstrip(".")


async def find_relevant_facts(claim: str, limit: int = 8) -> list[dict[str, Any]]:
    terms = [t for t in re.findall(r"[a-zA-Z0-9]{4,}", normalize_fact(claim))][:8]
    if not terms:
        return []
    where = " OR ".join("normalized_text LIKE ?" for _ in terms)
    db = await get_db()
    try:
        cursor = await db.execute(
            f"SELECT * FROM facts WHERE status = 'ACCEPTED' AND ({where}) LIMIT ?",
            tuple(f"%{term}%" for term in terms) + (limit,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def store_proposal_evidence(proposal_id: str, sources: list[Source], query: str = "") -> None:
    db = await get_db()
    try:
        for rank, source in enumerate(sources, start=1):
            cursor = await db.execute("SELECT id FROM sources WHERE url = ?", (source.url,))
            row = await cursor.fetchone()
            source_id = row["id"] if row else f"SRC-{uuid.uuid4().hex[:12]}"
            if not row:
                await db.execute(
                    "INSERT INTO sources (id, url, title, domain) VALUES (?, ?, ?, ?)",
                    (source_id, source.url, source.title, source.domain),
                )
            await db.execute(
                "INSERT OR REPLACE INTO proposal_evidence (proposal_id, source_id, snippet, query, rank) VALUES (?, ?, ?, ?, ?)",
                (proposal_id, source_id, source.snippet, query, rank),
            )
        await db.commit()
    finally:
        await db.close()


async def accept_fact(proposal_id: str, claim: str, sources: list[Source], reason: str = "") -> tuple[bool, str]:
    normalized = normalize_fact(claim)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM facts WHERE normalized_text = ?", (normalized,))
        row = await cursor.fetchone()
        created = row is None
        fact_id = row["id"] if row else f"FACT-{uuid.uuid4().hex[:12]}"
        if created:
            await db.execute(
                "INSERT INTO facts (id, fact_text, normalized_text, accepted_proposal_id) VALUES (?, ?, ?, ?)",
                (fact_id, claim, normalized, proposal_id),
            )
        for source in sources:
            cursor = await db.execute("SELECT id FROM sources WHERE url = ?", (source.url,))
            source_row = await cursor.fetchone()
            if not source_row:
                continue
            await db.execute(
                "INSERT OR IGNORE INTO fact_sources (fact_id, source_id) VALUES (?, ?)",
                (fact_id, source_row["id"]),
            )
        await db.execute(
            "INSERT INTO fact_history (fact_id, proposal_id, action, reason) VALUES (?, ?, ?, ?)",
            (fact_id, proposal_id, "ACCEPTED" if created else "DUPLICATE_ACCEPT", reason),
        )
        await db.commit()
        return created, fact_id
    finally:
        await db.close()

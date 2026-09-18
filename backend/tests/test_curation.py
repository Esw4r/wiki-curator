"""Upstream pipeline tests; all external search and Groq boundaries are faked."""

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend.agents.editor_agent import EditorAgent
from backend.agents.research_agent import ResearchAgent
from backend.database import kb_models
from backend.database import models as review_db
from backend.database.db import init_db
from backend.schemas.curation import ClaimSubmission
from backend.schemas.messages import (
    ConsensusDecision, EditorVerdictType, ProposalDetail, ResearchOutput, Source, VoteChoice,
)
from backend.services.curation_orchestrator import CurationOrchestrator


@pytest_asyncio.fixture
async def isolated_db(tmp_path, monkeypatch):
    from backend import config
    old = config._YAML.get("database", {}).get("path")
    config._YAML.setdefault("database", {})["path"] = str(tmp_path / "test.db")
    await init_db()
    yield
    if old is None:
        config._YAML["database"].pop("path", None)
    else:
        config._YAML["database"]["path"] = old


def test_claim_submission_validation():
    assert ClaimSubmission(claim="A factual claim").claim == "A factual claim"
    with pytest.raises(ValueError):
        ClaimSubmission(claim="no")


@pytest.mark.asyncio
async def test_research_agent_uses_search_results():
    source = Source(title="Official", url="https://example.org/a", snippet="Evidence", domain="example.org")
    search = AsyncMock()
    search.search.return_value = [source]
    result = await ResearchAgent(search=search).research("Example claim", "P-test")
    assert result.proposal_id == "P-test"
    assert result.sources == [source]
    search.search.assert_awaited_once_with("Example claim")


@pytest.mark.asyncio
async def test_editor_validates_mocked_groq_response():
    source = Source(title="Official", url="https://example.org/a", snippet="Evidence", domain="example.org")
    llm = AsyncMock()
    llm.json_completion.return_value = {"verdict": "VALID", "confidence": 0.9, "supporting_source_indexes": [0], "conflicts": [], "reason": "Direct support."}
    verdict = await EditorAgent(llm=llm).evaluate(ResearchOutput(proposal_id="P1", claim="Claim", sources=[source]), ["Existing fact"])
    assert verdict.verdict == EditorVerdictType.VALID
    assert verdict.supporting_sources == [source]


@pytest.mark.asyncio
async def test_kb_evidence_and_accepted_fact_relationship(isolated_db):
    source = Source(title="Official", url="https://example.org/a", snippet="Evidence", domain="example.org")
    await review_db.create_proposal("P1", "Earth is round.")
    await kb_models.store_proposal_evidence("P1", [source])
    created, fact_id = await kb_models.accept_fact("P1", "Earth is round.", [source])
    assert created is True
    relevant = await kb_models.find_relevant_facts("Earth is round")
    assert relevant[0]["id"] == fact_id


@pytest.mark.asyncio
async def test_orchestrator_updates_kb_only_after_accept(isolated_db, monkeypatch):
    source = Source(title="Official", url="https://example.org/a", snippet="Evidence", domain="example.org")
    research = AsyncMock(); research.research.return_value = ResearchOutput(proposal_id="P-ignored", claim="Earth is round.", sources=[source])
    editor = AsyncMock()
    from backend.schemas.messages import EditorVerdict
    editor.evaluate.return_value = EditorVerdict(proposal_id="P-ignored", claim="Earth is round.", verdict="VALID", confidence=.9, supporting_sources=[source])
    review = ProposalDetail(proposal_id="P-ignored", claim="Earth is round.", consensus=ConsensusDecision(proposal_id="P-ignored", decision=VoteChoice.ACCEPT))
    monkeypatch.setattr("backend.services.curation_orchestrator.submit_for_review", AsyncMock(return_value=review))
    result = await CurationOrchestrator(research=research, editor=editor).submit_claim("Earth is round.")
    assert result.kb_updated is True
    assert result.kb_fact_id


@pytest.mark.asyncio
async def test_orchestrator_does_not_update_kb_after_reject(isolated_db, monkeypatch):
    source = Source(title="Official", url="https://example.org/reject", snippet="Evidence", domain="example.org")
    research = AsyncMock(); research.research.return_value = ResearchOutput(proposal_id="P-ignored", claim="Unsupported claim.", sources=[source])
    editor = AsyncMock()
    from backend.schemas.messages import EditorVerdict
    editor.evaluate.return_value = EditorVerdict(proposal_id="P-ignored", claim="Unsupported claim.", verdict="CONTRADICTED", confidence=.9, supporting_sources=[source])
    review = ProposalDetail(proposal_id="P-ignored", claim="Unsupported claim.", consensus=ConsensusDecision(proposal_id="P-ignored", decision=VoteChoice.REJECT))
    monkeypatch.setattr("backend.services.curation_orchestrator.submit_for_review", AsyncMock(return_value=review))
    result = await CurationOrchestrator(research=research, editor=editor).submit_claim("Unsupported claim.")
    assert result.kb_updated is False
    assert await kb_models.find_relevant_facts("Unsupported claim") == []


def test_curation_endpoint_with_fake_orchestrator(monkeypatch):
    from backend.main import app
    from backend.api import curation_routes
    fake = AsyncMock()
    fake.submit_claim.return_value = {
        "proposal_id": "P1", "claim": "Earth is round.", "kb_context": {"facts": [], "duplicate_fact_ids": []},
        "research": {"proposal_id": "P1", "claim": "Earth is round.", "sources": []},
        "editor_verdict": {"proposal_id": "P1", "claim": "Earth is round.", "verdict": "INSUFFICIENT_EVIDENCE", "confidence": 0, "supporting_sources": [], "conflicts": [], "reason": "", "existing_kb_facts": []},
        "review": {"proposal_id": "P1", "claim": "Earth is round.", "status": "NEEDS_MORE_EVIDENCE", "votes": [], "byzantine_active": False}, "kb_updated": False,
    }
    monkeypatch.setattr(curation_routes, "_orchestrator", fake)
    response = TestClient(app).post("/api/curation", json={"claim": "Earth is round."})
    assert response.status_code == 200

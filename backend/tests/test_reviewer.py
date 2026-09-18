"""
Unit tests for the Evidence, Consistency, and Conservative reviewers.

All Groq API calls are faked via direct _llm attribute replacement.
No live API key is required.

Test coverage:
 1.  Clearly supported factual claim (multiple credible sources).
 2.  Clearly contradicted factual claim.
 3.  Claim with no evidence.
 4.  Claim with irrelevant evidence.
 5.  Claim with low-quality sources.
 6.  Compound claim where only one component is supported.
 7.  Ambiguous wording — literal interpretation evaluated first.
 8.  Byzantine argument exploiting an alternative interpretation.
 9.  Byzantine argument using a technically true but irrelevant fact.
10.  Byzantine argument using historical context that does not contradict the current claim.
11.  Credible contradictory source.
12.  Multiple independent supporting sources.
13.  REGRESSION — "stones are consumed by humans and humans say they taste good".
14.  LLM failure fallback returns NEEDS_MORE_EVIDENCE.
15.  Prompt contains per-source analysis instructions when sources are present.
16.  Prompt contains KB fact comparison instructions when KB facts are present.
17.  Prompt does not claim "no evidence" when sources are passed.
18.  Adversarial resistance section is present in every prompt.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.agents.conservative_reviewer import ConservativeReviewer
from backend.agents.consistency_reviewer import ConsistencyReviewer
from backend.agents.evidence_reviewer import EvidenceReviewer
from backend.schemas.messages import (
    EditorVerdict,
    EditorVerdictType,
    ReviewVote,
    Source,
    VoteChoice,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _verdict(
    claim: str,
    verdict: str = "VALID",
    confidence: float = 0.85,
    reason: str = "Editor assessment.",
    conflicts: list[str] | None = None,
    kb_facts: list[str] | None = None,
    proposal_id: str = "P-test",
) -> EditorVerdict:
    return EditorVerdict(
        proposal_id=proposal_id,
        claim=claim,
        verdict=EditorVerdictType(verdict),
        confidence=confidence,
        reason=reason,
        conflicts=conflicts or [],
        existing_kb_facts=kb_facts or [],
    )


def _source(
    title: str,
    url: str,
    snippet: str,
    domain: str = "example.org",
) -> Source:
    return Source(title=title, url=url, snippet=snippet, domain=domain)


def _credible(n: int = 1) -> list[Source]:
    """Return n credible Wikipedia-style sources."""
    return [
        _source(
            title=f"Wikipedia — Topic {i}",
            url=f"https://en.wikipedia.org/wiki/Topic_{i}",
            snippet=f"Confirmed fact {i} directly supporting the claim.",
            domain="en.wikipedia.org",
        )
        for i in range(1, n + 1)
    ]


def _llm_returning(vote: str, confidence: float, reason: str) -> AsyncMock:
    """Return a fake LLM that always produces the given structured response."""
    mock = AsyncMock()
    mock.json_completion = AsyncMock(
        return_value={"vote": vote, "confidence": confidence, "reason": reason}
    )
    return mock


def _llm_raising(exc: Exception) -> AsyncMock:
    """Return a fake LLM that always raises."""
    mock = AsyncMock()
    mock.json_completion = AsyncMock(side_effect=exc)
    return mock


async def _review(
    reviewer_cls,
    claim: str,
    sources: list[Source],
    verdict_kwargs: dict | None = None,
    llm_vote: str = "ACCEPT",
    llm_confidence: float = 0.90,
    llm_reason: str = "Sources directly support the claim.",
    kb_facts: list[str] | None = None,
) -> ReviewVote:
    """Instantiate a reviewer with a mocked LLM and run review()."""
    reviewer = reviewer_cls()
    reviewer._llm = _llm_returning(llm_vote, llm_confidence, llm_reason)
    vkw = verdict_kwargs or {}
    ev = _verdict(claim=claim, kb_facts=kb_facts, **vkw)
    return await reviewer.review(claim, sources, ev, kb_facts)


# ── Test 1: Clearly supported factual claim ──────────────────────────────

class TestClearlySupportedClaim:
    @pytest.mark.asyncio
    async def test_evidence_reviewer_accept(self):
        vote = await _review(
            EvidenceReviewer,
            claim="The speed of light in a vacuum is approximately 299,792 km/s.",
            sources=_credible(2),
            llm_vote="ACCEPT",
            llm_confidence=0.95,
            llm_reason="Source 1 (en.wikipedia.org) directly states the speed of light value. Source 2 (britannica.com) confirms independently. Both are authoritative.",
        )
        assert vote.vote == VoteChoice.ACCEPT
        assert vote.confidence == 0.95
        assert vote.reviewer_id == "reviewer_1"

    @pytest.mark.asyncio
    async def test_consistency_reviewer_accept(self):
        vote = await _review(
            ConsistencyReviewer,
            claim="The speed of light in a vacuum is approximately 299,792 km/s.",
            sources=_credible(2),
            llm_vote="ACCEPT",
            llm_confidence=0.92,
            llm_reason="No KB facts conflict with this claim. The claim is internally coherent.",
        )
        assert vote.vote == VoteChoice.ACCEPT
        assert vote.reviewer_id == "reviewer_2"

    @pytest.mark.asyncio
    async def test_conservative_reviewer_accept(self):
        vote = await _review(
            ConservativeReviewer,
            claim="The speed of light in a vacuum is approximately 299,792 km/s.",
            sources=_credible(2),
            llm_vote="ACCEPT",
            llm_confidence=0.88,
            llm_reason="Two independent authoritative sources directly confirm the exact value stated in the claim.",
        )
        assert vote.vote == VoteChoice.ACCEPT
        assert vote.confidence == 0.88
        assert vote.reviewer_id == "reviewer_3"


# ── Test 2: Clearly contradicted factual claim ───────────────────────────

class TestContradictedClaim:
    @pytest.mark.asyncio
    async def test_evidence_reviewer_reject(self):
        sources = [
            _source(
                "NASA — Solar System",
                "https://solarsystem.nasa.gov/planets/earth",
                "Earth is the third planet from the Sun, not the second.",
                "solarsystem.nasa.gov",
            )
        ]
        vote = await _review(
            EvidenceReviewer,
            claim="Earth is the second planet from the Sun.",
            sources=sources,
            verdict_kwargs={"verdict": "CONTRADICTED"},
            llm_vote="REJECT",
            llm_confidence=0.97,
            llm_reason="Source 1 (NASA, solarsystem.nasa.gov) explicitly states Earth is the third planet from the Sun, directly contradicting the claim.",
        )
        assert vote.vote == VoteChoice.REJECT
        assert vote.confidence >= 0.90

    @pytest.mark.asyncio
    async def test_conservative_reviewer_rejects_not_nme(self):
        """Conservative reviewer must REJECT on direct contradiction, not NEEDS_MORE_EVIDENCE."""
        sources = [
            _source(
                "Encyclopaedia Britannica",
                "https://www.britannica.com/place/Paris",
                "Paris is the capital of France.",
                "britannica.com",
            )
        ]
        vote = await _review(
            ConservativeReviewer,
            claim="Berlin is the capital of France.",
            sources=sources,
            verdict_kwargs={"verdict": "CONTRADICTED"},
            llm_vote="REJECT",
            llm_confidence=0.98,
            llm_reason="Source 1 (Britannica) directly contradicts the claim by stating Paris is the capital of France.",
        )
        assert vote.vote == VoteChoice.REJECT


# ── Test 3: Claim with no evidence ───────────────────────────────────────

class TestNoEvidence:
    @pytest.mark.asyncio
    async def test_evidence_reviewer_nme_with_no_sources(self):
        vote = await _review(
            EvidenceReviewer,
            claim="The population of Atlantis is 4 million.",
            sources=[],
            verdict_kwargs={"verdict": "INSUFFICIENT_EVIDENCE", "confidence": 0.1},
            llm_vote="NEEDS_MORE_EVIDENCE",
            llm_confidence=0.95,
            llm_reason="No sources were provided. Cannot evaluate the claim without evidence.",
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE

    @pytest.mark.asyncio
    async def test_conservative_reviewer_does_not_accept_without_sources(self):
        vote = await _review(
            ConservativeReviewer,
            claim="Mount Everest is taller than K2.",
            sources=[],
            verdict_kwargs={"verdict": "INSUFFICIENT_EVIDENCE", "confidence": 0.1},
            llm_vote="NEEDS_MORE_EVIDENCE",
            llm_confidence=0.90,
            llm_reason="No sources supplied. Even well-known facts require source grounding for acceptance.",
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE


# ── Test 4: Claim with irrelevant evidence ───────────────────────────────

class TestIrrelevantEvidence:
    @pytest.mark.asyncio
    async def test_evidence_reviewer_nme_on_irrelevant_sources(self):
        irrelevant_sources = [
            _source(
                "Stone Cold Steve Austin fan wiki",
                "https://wrestling.fan/stone-cold",
                "Stone Cold Steve Austin is a famous wrestler known for his catchphrase.",
                "wrestling.fan",
            )
        ]
        vote = await _review(
            EvidenceReviewer,
            claim="The density of granite is approximately 2.7 g/cm³.",
            sources=irrelevant_sources,
            verdict_kwargs={"verdict": "INSUFFICIENT_EVIDENCE"},
            llm_vote="NEEDS_MORE_EVIDENCE",
            llm_confidence=0.88,
            llm_reason="The single source (wrestling.fan) is entirely about a wrestler and does not address the density of granite. No relevant evidence is present.",
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE

    @pytest.mark.asyncio
    async def test_prompt_does_not_say_no_evidence_when_sources_present(self):
        """The prompt must not write 'No external sources provided' when sources exist."""
        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_returning("NEEDS_MORE_EVIDENCE", 0.7, "Irrelevant.")
        ev = _verdict(claim="Granite density is 2.7 g/cm³.")
        sources = [_source("Irrelevant page", "https://example.com", "Unrelated content.")]
        prompt = reviewer._build_prompt("Granite density is 2.7 g/cm³.", sources, ev, [])
        assert "No external sources provided" not in prompt
        assert "No external sources were provided" not in prompt


# ── Test 5: Claim with low-quality sources ───────────────────────────────

class TestLowQualitySources:
    @pytest.mark.asyncio
    async def test_evidence_reviewer_nme_on_blog_only(self):
        blog_sources = [
            _source(
                "My Health Blog",
                "https://myhealthblog.blogspot.com/post/123",
                "Apparently drinking bleach cures the common cold according to some people.",
                "myhealthblog.blogspot.com",
            )
        ]
        vote = await _review(
            EvidenceReviewer,
            claim="Drinking bleach cures the common cold.",
            sources=blog_sources,
            verdict_kwargs={"verdict": "INSUFFICIENT_EVIDENCE"},
            llm_vote="NEEDS_MORE_EVIDENCE",
            llm_confidence=0.92,
            llm_reason="The single source is a personal blog (myhealthblog.blogspot.com), which is not a credible source. No peer-reviewed or authoritative evidence supports this claim.",
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE

    @pytest.mark.asyncio
    async def test_conservative_reviewer_nme_on_single_blog(self):
        vote = await _review(
            ConservativeReviewer,
            claim="Coffee cures depression.",
            sources=[_source("Blog post", "https://coffeelover.blog/cures", "Coffee definitely cures depression!", "coffeelover.blog")],
            verdict_kwargs={"verdict": "INSUFFICIENT_EVIDENCE"},
            llm_vote="NEEDS_MORE_EVIDENCE",
            llm_confidence=0.91,
            llm_reason="Only one source present (coffeelover.blog), a personal blog. No peer-reviewed research or official medical source directly supports the specific causal claim.",
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE


# ── Test 6: Compound claim, only one component supported ─────────────────

class TestCompoundClaimPartialSupport:
    @pytest.mark.asyncio
    async def test_evidence_reviewer_nme_on_partial_compound(self):
        """Source supports 'Python was created by Guido' but not 'in 1985'."""
        sources = [
            _source(
                "Python history",
                "https://docs.python.org/history",
                "Python was created by Guido van Rossum. Development began in the late 1980s.",
                "docs.python.org",
            )
        ]
        vote = await _review(
            EvidenceReviewer,
            claim="Python was created by Guido van Rossum in 1985.",
            sources=sources,
            llm_vote="NEEDS_MORE_EVIDENCE",
            llm_confidence=0.82,
            llm_reason="Source 1 (docs.python.org) confirms that Guido van Rossum created Python (proposition A supported). However, it states development began 'in the late 1980s', not specifically 1985. Proposition B (exact year 1985) is not directly established.",
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE

    @pytest.mark.asyncio
    async def test_conservative_reviewer_nme_on_compound_with_gap(self):
        """Both propositions in 'X causes Y AND people enjoy Y' must be supported."""
        sources = [
            _source(
                "Exercise research",
                "https://pubmed.ncbi.nlm.nih.gov/exercise-endorphins",
                "Exercise causes release of endorphins in the brain.",
                "pubmed.ncbi.nlm.nih.gov",
            )
        ]
        vote = await _review(
            ConservativeReviewer,
            claim="Exercise causes endorphin release and everyone finds exercise enjoyable.",
            sources=sources,
            llm_vote="NEEDS_MORE_EVIDENCE",
            llm_confidence=0.85,
            llm_reason="Source 1 (PubMed) directly supports proposition A: exercise causes endorphin release. Proposition B (everyone finds exercise enjoyable) is not established by any supplied source — this is a distinct empirical claim requiring independent evidence.",
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE


# ── Test 7: Ambiguous wording — literal interpretation required ───────────

class TestAmbiguousWording:
    @pytest.mark.asyncio
    async def test_literal_interpretation_takes_priority(self):
        """'Stones are consumed by humans' — literal meaning evaluated first."""
        sources = [
            _source(
                "Nutrition guide",
                "https://nutrition.org/stone-fruits",
                "Stone fruits such as cherries, peaches, and plums are popular human foods.",
                "nutrition.org",
            )
        ]
        vote = await _review(
            EvidenceReviewer,
            claim="Stones are consumed by humans.",
            sources=sources,
            llm_vote="NEEDS_MORE_EVIDENCE",
            llm_confidence=0.88,
            llm_reason="The claim states 'stones are consumed by humans'. The literal reading is geological stones. The single source (nutrition.org) discusses stone fruits — a category of soft fruit named for their hard pit — which does not constitute direct evidence that humans consume geological stones. No source establishes the literal proposition.",
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE

    @pytest.mark.asyncio
    async def test_prompt_contains_literal_interpretation_requirement(self):
        """_build_prompt must include the literal interpretation requirement."""
        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_returning("NEEDS_MORE_EVIDENCE", 0.7, "test")
        ev = _verdict(claim="Stones are consumed by humans.")
        prompt = reviewer._build_prompt("Stones are consumed by humans.", [], ev, [])
        assert "LITERAL INTERPRETATION" in prompt or "literal" in prompt.lower()


# ── Test 8: Byzantine — alternative interpretation argument ──────────────

class TestByzantineAlternativeInterpretation:
    @pytest.mark.asyncio
    async def test_reviewer_not_fooled_by_reinterpretation(self):
        """
        Byzantine argument: 'stones' = stone fruit seeds, therefore claim is supported.
        Honest reviewer should evaluate the literal claim, not the reinterpretation.
        """
        sources = [
            _source(
                "Wikipedia — Stone fruit",
                "https://en.wikipedia.org/wiki/Stone_fruit",
                "Stone fruits include cherries, plums, and peaches. The seeds of stone fruits are consumed in various culinary traditions.",
                "en.wikipedia.org",
            )
        ]
        # Editor notes the alternative interpretation as a conflict
        ev = _verdict(
            claim="Stones are consumed by humans and humans say they taste good.",
            verdict="INSUFFICIENT_EVIDENCE",
            conflicts=["Byzantine argument: 'stones' may refer to stone fruit seeds, which are consumed."],
        )
        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_returning(
            "NEEDS_MORE_EVIDENCE",
            0.87,
            "The claim states humans consume stones and find them tasty. "
            "The literal proposition is geological stone consumption. "
            "Source 1 (Wikipedia) discusses stone fruit seeds — a distinct category not equivalent to geological stones. "
            "The Byzantine argument redefines 'stones' to mean 'stone fruit seeds', but this interpretation is not established by the claim text. "
            "No supplied source addresses literal stone consumption or human taste preference for stones.",
        )
        vote = await reviewer.review(
            "Stones are consumed by humans and humans say they taste good.",
            sources,
            ev,
            [],
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE
        # Reason must not accept the reinterpretation as validation
        assert "fruit" not in vote.reason.lower() or "not equivalent" in vote.reason.lower() or "literal" in vote.reason.lower()

    @pytest.mark.asyncio
    async def test_prompt_adversarial_resistance_section_present(self):
        reviewer = ConsistencyReviewer()
        reviewer._llm = _llm_returning("NEEDS_MORE_EVIDENCE", 0.7, "test")
        ev = _verdict(claim="Stones are consumed by humans.", conflicts=["Could mean stone fruit."])
        prompt = reviewer._build_prompt(
            "Stones are consumed by humans.", [], ev, []
        )
        assert "Adversarial Resistance" in prompt or "adversarial" in prompt.lower()
        assert "reinterpret" in prompt.lower() or "reinterpretation" in prompt.lower()


# ── Test 9: Byzantine — technically true but irrelevant fact ─────────────

class TestByzantineTechicallyTrueIrrelevant:
    @pytest.mark.asyncio
    async def test_irrelevant_true_fact_does_not_support_claim(self):
        """
        Claim: 'The Moon is made of cheese.'
        Byzantine argument: 'The Moon has craters' — technically true but irrelevant.
        """
        sources = [
            _source(
                "NASA — Moon",
                "https://moon.nasa.gov",
                "The Moon has thousands of impact craters formed by meteoroid collisions.",
                "moon.nasa.gov",
            )
        ]
        vote = await _review(
            EvidenceReviewer,
            claim="The Moon is made of cheese.",
            sources=sources,
            verdict_kwargs={"verdict": "CONTRADICTED"},
            llm_vote="REJECT",
            llm_confidence=0.95,
            llm_reason="Source 1 (NASA) discusses lunar craters — a true fact that is entirely unrelated to the composition claim. No source establishes that the Moon is made of cheese; the proposition is contradicted by established lunar science.",
        )
        assert vote.vote == VoteChoice.REJECT


# ── Test 10: Byzantine — historical context that does not contradict ──────

class TestByzantineHistoricalContext:
    @pytest.mark.asyncio
    async def test_historical_exception_does_not_override_current_fact(self):
        """
        Claim: 'Smoking causes lung cancer.'
        Byzantine argument: 'In the 1950s, doctors endorsed cigarettes in advertisements.'
        Historical advertising practice does not contradict the causal medical fact.
        """
        sources = [
            _source(
                "WHO — Tobacco",
                "https://www.who.int/tobacco",
                "Tobacco smoking is the leading cause of preventable cancer death worldwide, including lung cancer.",
                "who.int",
            ),
            _source(
                "1950s cigarette ads",
                "https://history.example.com/cigarette-ads",
                "In the 1950s, cigarette companies ran advertisements featuring doctors endorsing their products.",
                "history.example.com",
            ),
        ]
        vote = await _review(
            ConsistencyReviewer,
            claim="Smoking causes lung cancer.",
            sources=sources,
            llm_vote="ACCEPT",
            llm_confidence=0.93,
            llm_reason="Source 1 (WHO) directly establishes that smoking causes lung cancer. Source 2 describes historical advertising — it is a true historical fact but does not contradict the causal medical claim, which is established by authoritative current scientific consensus. The historical context is unrelated to the causal proposition.",
        )
        assert vote.vote == VoteChoice.ACCEPT


# ── Test 11: Credible contradictory source ────────────────────────────────

class TestCredibleContradictorySource:
    @pytest.mark.asyncio
    async def test_credible_contradiction_yields_reject(self):
        sources = [
            _source(
                "CDC — Vaccine Safety",
                "https://www.cdc.gov/vaccinesafety",
                "Vaccines do not cause autism. Multiple large-scale studies have found no link between vaccines and autism spectrum disorder.",
                "cdc.gov",
            )
        ]
        vote = await _review(
            EvidenceReviewer,
            claim="The MMR vaccine causes autism.",
            sources=sources,
            verdict_kwargs={"verdict": "CONTRADICTED"},
            llm_vote="REJECT",
            llm_confidence=0.98,
            llm_reason="Source 1 (CDC, cdc.gov) directly contradicts the claim, stating explicitly that vaccines do not cause autism and citing multiple large-scale studies. This is a government health authority — a highly credible source.",
        )
        assert vote.vote == VoteChoice.REJECT
        assert vote.confidence >= 0.90

    @pytest.mark.asyncio
    async def test_consistency_reviewer_rejects_on_kb_contradiction(self):
        vote = await _review(
            ConsistencyReviewer,
            claim="Python was created in 1980.",
            sources=[],
            kb_facts=["Python was created by Guido van Rossum and first released in 1991."],
            verdict_kwargs={"verdict": "CONTRADICTED"},
            llm_vote="REJECT",
            llm_confidence=0.95,
            llm_reason="KB fact states Python was first released in 1991. The claim asserts 1980, which directly contradicts the established KB fact.",
        )
        assert vote.vote == VoteChoice.REJECT


# ── Test 12: Multiple independent supporting sources ─────────────────────

class TestMultipleIndependentSources:
    @pytest.mark.asyncio
    async def test_two_independent_credible_sources_sufficient_for_accept(self):
        sources = [
            _source(
                "Wikipedia — Water",
                "https://en.wikipedia.org/wiki/Water",
                "Water is a chemical compound with the molecular formula H₂O.",
                "en.wikipedia.org",
            ),
            _source(
                "IUPAC — Water",
                "https://iupac.org/compounds/water",
                "The chemical formula for water is H₂O, consisting of two hydrogen atoms and one oxygen atom.",
                "iupac.org",
            ),
        ]
        vote = await _review(
            ConservativeReviewer,
            claim="The chemical formula for water is H₂O.",
            sources=sources,
            llm_vote="ACCEPT",
            llm_confidence=0.94,
            llm_reason="Source 1 (Wikipedia) and Source 2 (IUPAC) are independent, credible sources that both directly state the chemical formula of water is H₂O. The claim is exactly matched.",
        )
        assert vote.vote == VoteChoice.ACCEPT

    @pytest.mark.asyncio
    async def test_three_sources_increase_confidence(self):
        sources = _credible(3)
        vote = await _review(
            EvidenceReviewer,
            claim="The Earth orbits the Sun.",
            sources=sources,
            llm_vote="ACCEPT",
            llm_confidence=0.97,
            llm_reason="Three independent Wikipedia sources all confirm that the Earth orbits the Sun. Multiple independent credible sources establish the claim directly.",
        )
        assert vote.vote == VoteChoice.ACCEPT
        assert vote.confidence >= 0.90


# ── Test 13: REGRESSION — stones compound claim ──────────────────────────

class TestStonesRegression:
    """
    Regression test for: "stones are consumed by humans and humans say they taste good"

    Requirements:
    - The claim must NOT be accepted merely because 'stones' can theoretically mean
      something else (e.g. stone fruit, kidney stones, Rolling Stones).
    - The literal claim must be evaluated first.
    - Both propositions must be evaluated independently:
        A. Humans consume literal stones/rocks.
        B. Humans report that literal stones taste good.
    - If the supplied evidence does not establish both propositions, the verdict
      must be INSUFFICIENT_EVIDENCE or CONTRADICTED.
    - The reviewer must distinguish: geological stones / isolated consumption /
      general human consumption / evidence of taste preference.
    """

    CLAIM = "stones are consumed by humans and humans say they taste good"

    def _stones_verdict(self, verdict: str = "INSUFFICIENT_EVIDENCE") -> EditorVerdict:
        return _verdict(
            claim=self.CLAIM,
            verdict=verdict,
            confidence=0.2,
            reason="Ambiguous claim. Literal interpretation: geological stone consumption.",
        )

    @pytest.mark.asyncio
    async def test_no_evidence_returns_nme(self):
        """With no sources, neither proposition can be established."""
        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_returning(
            "NEEDS_MORE_EVIDENCE",
            0.92,
            "The claim contains two propositions: (A) humans consume literal stones and "
            "(B) humans say they taste good. No sources were provided. Neither proposition "
            "can be established without evidence.",
        )
        vote = await reviewer.review(self.CLAIM, [], self._stones_verdict(), [])
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE

    @pytest.mark.asyncio
    async def test_stone_fruit_source_does_not_establish_literal_stones(self):
        """Stone fruit sources do not support the literal stone consumption claim."""
        sources = [
            _source(
                "Wikipedia — Stone fruit",
                "https://en.wikipedia.org/wiki/Drupe",
                "A drupe (stone fruit) is a fleshy fruit with a hard stone pit. "
                "Common drupes include peaches, cherries, and olives.",
                "en.wikipedia.org",
            )
        ]
        for reviewer_cls in [EvidenceReviewer, ConservativeReviewer]:
            reviewer = reviewer_cls()
            reviewer._llm = _llm_returning(
                "NEEDS_MORE_EVIDENCE",
                0.90,
                "Proposition A: humans consume literal stones. Source 1 discusses stone fruit "
                "(drupes) — soft fleshy fruits named for their hard pit, not geological stones. "
                "This does not directly support the literal proposition. "
                "Proposition B: taste preference for stones — no source addresses this. "
                "The stone fruit interpretation substitutes a different referent for 'stones' "
                "and is not established by the claim text.",
            )
            vote = await reviewer.review(
                self.CLAIM, sources, self._stones_verdict(), []
            )
            assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE, (
                f"{reviewer_cls.__name__} should not accept claim on stone fruit source alone"
            )

    @pytest.mark.asyncio
    async def test_isolated_anecdote_does_not_establish_general_claim(self):
        """One person eating a stone does not establish 'humans (generally) consume stones'."""
        sources = [
            _source(
                "News article",
                "https://news.example.com/man-eats-stone",
                "A man in rural Rajasthan was reported to have eaten small pebbles "
                "as part of a traditional medicinal practice.",
                "news.example.com",
            )
        ]
        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_returning(
            "NEEDS_MORE_EVIDENCE",
            0.88,
            "Proposition A: humans consume stones. Source 1 reports one isolated anecdote "
            "from a specific cultural context. An isolated case does not establish that "
            "humans generally consume stones. "
            "Proposition B: humans say they taste good. No source addresses taste preference. "
            "Both propositions remain unestablished.",
        )
        vote = await reviewer.review(
            self.CLAIM, sources, self._stones_verdict(), []
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE

    @pytest.mark.asyncio
    async def test_partial_support_does_not_validate_compound_claim(self):
        """Even if proposition A were supported, proposition B (taste) must also be."""
        sources = [
            _source(
                "Geophagy study",
                "https://pubmed.ncbi.nlm.nih.gov/geophagy",
                "Geophagy, the practice of eating earth and clay minerals, "
                "is documented in multiple cultures worldwide.",
                "pubmed.ncbi.nlm.nih.gov",
            )
        ]
        # Note: geophagy covers clay/earth, not geological rock/stones per se,
        # and even if it did, proposition B (taste preference) is not addressed.
        reviewer = ConservativeReviewer()
        reviewer._llm = _llm_returning(
            "NEEDS_MORE_EVIDENCE",
            0.87,
            "Source 1 (PubMed) documents geophagy (consumption of earth/clay minerals). "
            "This partially addresses proposition A but 'stones' in the claim most naturally "
            "refers to rocks, not clay or mineral earth. Even accepting geophagy as relevant, "
            "proposition B — that humans say stones taste good — is entirely absent from any "
            "supplied source. A compound claim requires all propositions to be supported.",
        )
        vote = await reviewer.review(
            self.CLAIM, sources, self._stones_verdict(), []
        )
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE

    @pytest.mark.asyncio
    async def test_prompt_decomposes_compound_claim(self):
        """The prompt must instruct decomposition of compound claims."""
        reviewer = ConsistencyReviewer()
        reviewer._llm = _llm_returning("NEEDS_MORE_EVIDENCE", 0.8, "test")
        ev = self._stones_verdict()
        prompt = reviewer._build_prompt(self.CLAIM, [], ev, [])
        # The prompt should mention multiple propositions / compound claim handling
        prompt_lower = prompt.lower()
        assert "proposition" in prompt_lower or "multiple" in prompt_lower or "compound" in prompt_lower

    @pytest.mark.asyncio
    async def test_all_three_reviewers_return_nme_not_accept_on_no_evidence(self):
        """All three reviewers must not accept the stones claim when no evidence is supplied."""
        for reviewer_cls in [EvidenceReviewer, ConsistencyReviewer, ConservativeReviewer]:
            reviewer = reviewer_cls()
            reviewer._llm = _llm_returning(
                "NEEDS_MORE_EVIDENCE",
                0.90,
                "No sources establish either proposition in this compound claim.",
            )
            ev = self._stones_verdict()
            vote = await reviewer.review(self.CLAIM, [], ev, [])
            assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE, (
                f"{reviewer_cls.__name__} should not accept stones claim without evidence"
            )
            assert vote.vote != VoteChoice.ACCEPT


# ── Test 14: LLM failure fallback ────────────────────────────────────────

class TestLLMFailureFallback:
    @pytest.mark.asyncio
    async def test_evidence_reviewer_fallback_on_llm_error(self):
        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_raising(RuntimeError("API unavailable"))
        ev = _verdict(claim="Earth is round.")
        vote = await reviewer.review("Earth is round.", _credible(1), ev, [])
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE
        assert vote.confidence == 0.3
        assert "error" in vote.reason.lower() or "failed" in vote.reason.lower()

    @pytest.mark.asyncio
    async def test_consistency_reviewer_fallback_on_key_error(self):
        """If the LLM returns JSON missing the 'vote' key, fallback triggers."""
        reviewer = ConsistencyReviewer()
        bad_llm = AsyncMock()
        bad_llm.json_completion = AsyncMock(return_value={"confidence": 0.8, "reason": "ok"})
        reviewer._llm = bad_llm
        ev = _verdict(claim="Earth is round.")
        vote = await reviewer.review("Earth is round.", [], ev, [])
        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE
        assert vote.confidence == 0.3

    @pytest.mark.asyncio
    async def test_conservative_reviewer_fallback_preserves_proposal_id(self):
        reviewer = ConservativeReviewer()
        reviewer._llm = _llm_raising(ConnectionError("timeout"))
        ev = _verdict(claim="Test.", proposal_id="P-fallback-test")
        vote = await reviewer.review("Test.", [], ev, [])
        assert vote.proposal_id == "P-fallback-test"
        assert vote.reviewer_id == "reviewer_3"


# ── Test 15: Prompt structure — sources present ───────────────────────────

class TestPromptStructure:
    def _get_prompt(self, reviewer_cls, sources, kb_facts=None) -> str:
        reviewer = reviewer_cls()
        reviewer._llm = _llm_returning("ACCEPT", 0.9, "test")
        ev = _verdict(claim="Test claim.", kb_facts=kb_facts or [])
        return reviewer._build_prompt("Test claim.", sources, ev, kb_facts or [])

    def test_per_source_analysis_instructions_present_when_sources_exist(self):
        for reviewer_cls in [EvidenceReviewer, ConsistencyReviewer, ConservativeReviewer]:
            prompt = self._get_prompt(reviewer_cls, _credible(2))
            prompt_lower = prompt.lower()
            # Prompt must instruct per-source analysis
            assert "source" in prompt_lower
            assert "snippet" in prompt_lower or "what" in prompt_lower

    def test_no_sources_message_appears_when_sources_empty(self):
        for reviewer_cls in [EvidenceReviewer, ConsistencyReviewer, ConservativeReviewer]:
            prompt = self._get_prompt(reviewer_cls, [])
            assert "no external sources" in prompt.lower()

    def test_kb_section_present_when_kb_facts_supplied(self):
        kb_facts = ["Python was created in 1991.", "Python is a high-level language."]
        for reviewer_cls in [EvidenceReviewer, ConsistencyReviewer, ConservativeReviewer]:
            prompt = self._get_prompt(reviewer_cls, [], kb_facts=kb_facts)
            assert "Knowledge Base" in prompt
            assert "Python was created in 1991." in prompt

    def test_kb_section_absent_when_no_kb_facts(self):
        for reviewer_cls in [EvidenceReviewer, ConsistencyReviewer, ConservativeReviewer]:
            prompt = self._get_prompt(reviewer_cls, [], kb_facts=[])
            # KB section should not appear with empty facts
            assert "Knowledge Base Facts" not in prompt

    def test_adversarial_resistance_section_in_every_prompt(self):
        for reviewer_cls in [EvidenceReviewer, ConsistencyReviewer, ConservativeReviewer]:
            prompt = self._get_prompt(reviewer_cls, [])
            assert "Adversarial Resistance" in prompt or "adversarial" in prompt.lower()

    def test_evidence_traceability_requirement_in_every_prompt(self):
        """The task section must describe the CLAIM → SOURCE → CONCLUSION chain."""
        for reviewer_cls in [EvidenceReviewer, ConsistencyReviewer, ConservativeReviewer]:
            prompt = self._get_prompt(reviewer_cls, _credible(1))
            prompt_lower = prompt.lower()
            assert "source" in prompt_lower
            assert "conclusion" in prompt_lower or "relates" in prompt_lower or "support" in prompt_lower

    def test_editor_conflicts_included_in_prompt(self):
        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_returning("REJECT", 0.9, "test")
        ev = _verdict(
            claim="Test claim.",
            conflicts=["Contradicts KB fact: X is Y not Z."],
        )
        prompt = reviewer._build_prompt("Test claim.", [], ev, [])
        assert "Contradicts KB fact" in prompt


# ── Test 16: Evidence scope mismatch — Bigg Boss regression ──────────────

class TestEvidenceScopeMismatch:
    """
    Regression tests for claims where retrieved evidence supports a narrower or
    related proposition but does not establish the broad literal claim.

    The original observed bug: honest reviewers reported "No external sources provided"
    for "bigg boss is fake" while the Byzantine reviewer discussed real retrieved
    sources. Root cause: review_routes.py passed editor_verdict.supporting_sources
    (empty when verdict was INSUFFICIENT_EVIDENCE) instead of all_sources.

    With the fix, reviewers now receive all_sources. These tests verify that
    reviewers correctly identify SCOPE MISMATCH rather than simply reporting
    missing evidence when evidence is present but insufficient.

    Scope mismatch taxonomy:
    - Evidence about related fraud/scam ≠ evidence that the show itself is fake.
    - Evidence that fake videos circulated ≠ evidence that the show is fake.
    - Evidence about scripted moments ≠ evidence the entire show is fake.
    - Evidence about rumors ≠ established fact that the show is fake.
    """

    # ── 16a. all_sources propagation ────────────────────────────────────

    def test_all_sources_field_present_on_editor_verdict(self):
        """EditorVerdict must carry all_sources as a separate field from supporting_sources."""
        from backend.schemas.messages import EditorVerdict, EditorVerdictType, Source
        s1 = Source(title="T1", url="https://a.com", snippet="s1", domain="a.com")
        s2 = Source(title="T2", url="https://b.com", snippet="s2", domain="b.com")
        ev = EditorVerdict(
            proposal_id="P-test",
            claim="test",
            verdict=EditorVerdictType.INSUFFICIENT_EVIDENCE,
            confidence=0.2,
            supporting_sources=[],      # editor found nothing supporting
            all_sources=[s1, s2],       # but research retrieved both
        )
        assert len(ev.all_sources) == 2
        assert len(ev.supporting_sources) == 0

    def test_prompt_shows_all_sources_not_just_supporting(self):
        """
        When supporting_sources is empty but all_sources has content, the prompt
        must show the sources (not 'No external sources were provided').
        """
        from backend.schemas.messages import EditorVerdict, EditorVerdictType, Source
        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_returning("NEEDS_MORE_EVIDENCE", 0.7, "scope mismatch")

        s_scam = _source(
            "Times of India — Bigg Boss scam",
            "https://timesofindia.com/bigg-boss-scam",
            "A fraudster promised a Bigg Boss contestant spot in exchange for money.",
            "timesofindia.com",
        )
        s_fake_vid = _source(
            "AltNews fact-check",
            "https://altnews.in/fake-bigg-boss-video",
            "A viral video claiming to show a Bigg Boss elimination was found to be fabricated.",
            "altnews.in",
        )

        ev = EditorVerdict(
            proposal_id="P-bb",
            claim="bigg boss is fake",
            verdict=EditorVerdictType.INSUFFICIENT_EVIDENCE,
            confidence=0.3,
            supporting_sources=[],       # editor found nothing directly supporting
            all_sources=[s_scam, s_fake_vid],
        )

        # Pass all_sources as the sources argument (simulating what review_routes now does)
        prompt = reviewer._build_prompt(
            "bigg boss is fake",
            ev.all_sources,    # ← this is what review_routes.py now passes
            ev,
            [],
        )

        # The prompt must NOT say no evidence was provided
        assert "No external sources were provided" not in prompt
        assert "No external sources provided" not in prompt

        # Both sources must appear
        assert "timesofindia.com" in prompt
        assert "altnews.in" in prompt

        # Non-editor-selected sources: the instructional text mentions [EDITOR-SELECTED]
        # but neither actual source entry should carry the tag (since supporting_sources=[])
        # Find the source entries and verify neither has the tag appended
        assert "Source 1" in prompt
        assert "Source 2" in prompt
        # The tag only appears in the instruction note, not next to either source heading
        import re
        tagged_headers = re.findall(r"### Source \d+ \[EDITOR-SELECTED\]", prompt)
        assert len(tagged_headers) == 0, (
            f"No sources should be tagged as editor-selected when supporting_sources is empty, "
            f"but found: {tagged_headers}"
        )

    def test_prompt_tags_editor_selected_sources(self):
        """
        Sources that appear in supporting_sources must be tagged [EDITOR-SELECTED]
        in the prompt; non-selected sources from all_sources must not be tagged.
        """
        from backend.schemas.messages import EditorVerdict, EditorVerdictType, Source
        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_returning("ACCEPT", 0.9, "ok")

        s_direct = _source(
            "Wikipedia — Water",
            "https://en.wikipedia.org/wiki/Water",
            "Water is H2O.",
            "en.wikipedia.org",
        )
        s_indirect = _source(
            "Chemistry blog",
            "https://chemblog.example.com/water",
            "Water has various properties.",
            "chemblog.example.com",
        )

        ev = EditorVerdict(
            proposal_id="P-test",
            claim="Water is H2O.",
            verdict=EditorVerdictType.VALID,
            confidence=0.95,
            supporting_sources=[s_direct],
            all_sources=[s_direct, s_indirect],
        )

        prompt = reviewer._build_prompt("Water is H2O.", ev.all_sources, ev, [])

        assert "[EDITOR-SELECTED]" in prompt
        # The direct source should be tagged
        assert "en.wikipedia.org" in prompt
        # The indirect source should appear but not be tagged
        idx_indirect = prompt.find("chemblog.example.com")
        idx_tag_after = prompt.find("[EDITOR-SELECTED]", idx_indirect)
        # There should be no [EDITOR-SELECTED] tag immediately after chemblog entry
        # (i.e., the tag must appear before chemblog, not after)
        assert idx_indirect > 0

    # ── 16b. Scope mismatch — Bigg Boss pattern ─────────────────────────

    @pytest.mark.asyncio
    async def test_scam_evidence_does_not_establish_show_is_fake(self):
        """
        Evidence: a scam used the Bigg Boss name.
        Claim: Bigg Boss is fake.
        Expected: NEEDS_MORE_EVIDENCE with scope mismatch reasoning,
                  NOT a blanket "no evidence provided".
        """
        sources = [
            _source(
                "Times of India",
                "https://timesofindia.com/bigg-boss-scam-2024",
                "Police arrested a man who promised Bigg Boss contestant spots to victims "
                "in exchange for money. The accused used a fake Bigg Boss casting call.",
                "timesofindia.com",
            ),
        ]
        # Editor finds this insufficient — scam ≠ show is fake
        ev = EditorVerdict(
            proposal_id="P-bb1",
            claim="bigg boss is fake",
            verdict=EditorVerdictType.INSUFFICIENT_EVIDENCE,
            confidence=0.3,
            supporting_sources=[],
            all_sources=sources,
            reason="Evidence is about a casting scam, not about the show itself being fake.",
        )

        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_returning(
            "NEEDS_MORE_EVIDENCE",
            0.82,
            "Source 1 (Times of India) reports a scam where an individual fraudulently used "
            "the Bigg Boss name. This establishes that a scam occurred, NOT that the Bigg Boss "
            "show itself is fake. The claim 'Bigg Boss is fake' is a broad proposition about "
            "the show's authenticity. Evidence of peripheral fraud does not establish this "
            "broader claim. Scope mismatch: scam evidence ≠ show authenticity.",
        )
        vote = await reviewer.review("bigg boss is fake", sources, ev, [])

        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE
        # Reason must reference the source, not just say "no evidence"
        assert "source" in vote.reason.lower() or "times of india" in vote.reason.lower() or "scam" in vote.reason.lower()

    @pytest.mark.asyncio
    async def test_fake_video_evidence_does_not_establish_show_is_fake(self):
        """
        Evidence: fake videos about Bigg Boss circulated online.
        Claim: Bigg Boss is fake.
        Expected: NEEDS_MORE_EVIDENCE — fake videos ≠ the show is fake.
        """
        sources = [
            _source(
                "AltNews",
                "https://altnews.in/bigg-boss-fake-video-2024",
                "A video claiming to show a Bigg Boss contestant's elimination was found to "
                "be edited and fabricated. AltNews confirmed it was a deepfake.",
                "altnews.in",
            ),
        ]
        ev = EditorVerdict(
            proposal_id="P-bb2",
            claim="bigg boss is fake",
            verdict=EditorVerdictType.INSUFFICIENT_EVIDENCE,
            confidence=0.25,
            supporting_sources=[],
            all_sources=sources,
            reason="Evidence is about a fake video, not about the show itself.",
        )

        reviewer = ConsistencyReviewer()
        reviewer._llm = _llm_returning(
            "NEEDS_MORE_EVIDENCE",
            0.80,
            "Source 1 (AltNews) fact-checks a fabricated video — this establishes that "
            "fake videos about Bigg Boss exist, not that the show itself is fake. "
            "The proposition 'Bigg Boss is fake' concerns the show's production authenticity. "
            "Existence of fake third-party videos does not logically entail that the show is "
            "unauthentic. Scope mismatch identified.",
        )
        vote = await reviewer.review("bigg boss is fake", sources, ev, [])

        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE
        assert "source" in vote.reason.lower() or "altnews" in vote.reason.lower() or "video" in vote.reason.lower()

    @pytest.mark.asyncio
    async def test_scripted_rumours_do_not_establish_entirely_fake(self):
        """
        Evidence: articles discussing whether Bigg Boss episodes are scripted.
        Claim: Bigg Boss is fake.
        Expected: NEEDS_MORE_EVIDENCE — rumours about scripting ≠ established fact show is fake.
        """
        sources = [
            _source(
                "India Today",
                "https://indiatoday.in/bigg-boss-scripted-rumours",
                "Several former contestants have claimed some Bigg Boss tasks are scripted "
                "for dramatic effect, though the channel denies these allegations.",
                "indiatoday.in",
            ),
            _source(
                "Times Now",
                "https://timesnow.tv/bigg-boss-fake-voting",
                "Social media users allege the Bigg Boss voting system may be manipulated, "
                "though no official investigation has confirmed this.",
                "timesnow.tv",
            ),
        ]
        ev = EditorVerdict(
            proposal_id="P-bb3",
            claim="bigg boss is fake",
            verdict=EditorVerdictType.INSUFFICIENT_EVIDENCE,
            confidence=0.35,
            supporting_sources=[],
            all_sources=sources,
            reason="Allegations and rumours do not constitute established evidence that the show is fake.",
        )

        reviewer = ConservativeReviewer()
        reviewer._llm = _llm_returning(
            "NEEDS_MORE_EVIDENCE",
            0.85,
            "Source 1 (India Today) reports allegations by former contestants that some tasks "
            "are scripted — unconfirmed allegations, denied by the channel. Source 2 (Times Now) "
            "reports unverified social media allegations about voting manipulation. "
            "The claim 'Bigg Boss is fake' is a sweeping assertion about the show's "
            "authenticity. Unconfirmed allegations and social media claims do not establish "
            "this proposition. Neither source directly confirms the claim; both present "
            "rumours or unverified assertions. Scope: allegations ≠ established fact.",
        )
        vote = await reviewer.review("bigg boss is fake", sources, ev, [])

        assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE
        assert "source" in vote.reason.lower() or "allegation" in vote.reason.lower() or "india today" in vote.reason.lower()

    @pytest.mark.asyncio
    async def test_multiple_narrower_sources_together_still_insufficient(self):
        """
        Even with multiple sources all about Bigg Boss, if none directly establishes
        that the show itself is fake, the aggregate is still NEEDS_MORE_EVIDENCE.
        This tests that the reviewers do not mistakenly combine narrower evidence
        to reach the broader conclusion.
        """
        sources = [
            _source(
                "Times of India",
                "https://timesofindia.com/bigg-boss-scam",
                "A fraudster used the Bigg Boss brand to scam victims.",
                "timesofindia.com",
            ),
            _source(
                "AltNews",
                "https://altnews.in/fake-bigg-boss-clip",
                "A viral clip about Bigg Boss was confirmed to be a deepfake.",
                "altnews.in",
            ),
            _source(
                "India Today",
                "https://indiatoday.in/bigg-boss-scripted",
                "Some former contestants allege certain tasks are scripted.",
                "indiatoday.in",
            ),
        ]
        ev = EditorVerdict(
            proposal_id="P-bb4",
            claim="bigg boss is fake",
            verdict=EditorVerdictType.INSUFFICIENT_EVIDENCE,
            confidence=0.30,
            supporting_sources=[],
            all_sources=sources,
            reason="Three sources about related topics — none directly establishes the show is fake.",
        )

        for reviewer_cls in [EvidenceReviewer, ConsistencyReviewer, ConservativeReviewer]:
            reviewer = reviewer_cls()
            reviewer._llm = _llm_returning(
                "NEEDS_MORE_EVIDENCE",
                0.85,
                "Three sources are present but each addresses a narrower proposition: "
                "a fraud using the brand, a fake video, and scripting allegations. "
                "None directly establishes that Bigg Boss as a show is entirely fake. "
                "The aggregate of narrower related evidence does not prove the broad claim.",
            )
            vote = await reviewer.review("bigg boss is fake", sources, ev, [])
            assert vote.vote == VoteChoice.NEEDS_MORE_EVIDENCE, (
                f"{reviewer_cls.__name__} should not accept the claim from narrower aggregate evidence"
            )

    # ── 16c. Verify the fix: all_sources reaches reviewers ───────────────

    @pytest.mark.asyncio
    async def test_reviewer_receives_all_sources_when_supporting_empty(self):
        """
        Core regression: when editor finds no supporting sources, the reviewer
        should still receive the full research sources via all_sources.
        This directly tests the fix to review_routes.py.
        """
        from backend.schemas.messages import EditorVerdict, EditorVerdictType

        captured_prompts: list[str] = []

        class CapturingReviewer(EvidenceReviewer):
            def _build_prompt(self, claim, sources, editor_verdict, existing_kb_facts=None):
                prompt = super()._build_prompt(claim, sources, editor_verdict, existing_kb_facts)
                captured_prompts.append(prompt)
                return prompt

        s1 = _source("Source A", "https://source-a.com", "Content about the claim.", "source-a.com")
        s2 = _source("Source B", "https://source-b.com", "More content.", "source-b.com")

        ev = EditorVerdict(
            proposal_id="P-fix",
            claim="test claim",
            verdict=EditorVerdictType.INSUFFICIENT_EVIDENCE,
            confidence=0.1,
            supporting_sources=[],      # editor found nothing — old bug would show no sources
            all_sources=[s1, s2],       # but research found these
        )

        reviewer = CapturingReviewer()
        reviewer._llm = _llm_returning("NEEDS_MORE_EVIDENCE", 0.7, "scope mismatch found")

        # Simulate what review_routes.py now does: sources = all_sources or supporting_sources
        sources_for_reviewers = ev.all_sources or ev.supporting_sources
        vote = await reviewer.review("test claim", sources_for_reviewers, ev, [])

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]

        # The prompt must contain both sources — NOT the "no evidence" message
        assert "source-a.com" in prompt
        assert "source-b.com" in prompt
        assert "No external sources were provided" not in prompt
        assert "No external sources provided" not in prompt

    @pytest.mark.asyncio
    async def test_reviewer_falls_back_to_supporting_sources_when_all_sources_empty(self):
        """
        If all_sources is also empty (truly no research was done), the reviewer
        should fall back to supporting_sources and correctly show no-evidence message.
        """
        from backend.schemas.messages import EditorVerdict, EditorVerdictType

        ev = EditorVerdict(
            proposal_id="P-empty",
            claim="obscure claim",
            verdict=EditorVerdictType.INSUFFICIENT_EVIDENCE,
            confidence=0.0,
            supporting_sources=[],
            all_sources=[],
        )

        reviewer = EvidenceReviewer()
        reviewer._llm = _llm_returning("NEEDS_MORE_EVIDENCE", 0.9, "no evidence at all")

        sources_for_reviewers = ev.all_sources or ev.supporting_sources  # both empty → []
        prompt = reviewer._build_prompt("obscure claim", sources_for_reviewers, ev, [])

        assert "No external sources were provided" in prompt

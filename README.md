# Wiki Curator — Decentralized Knowledge Base Curation

A multi-agent, multi-model system where autonomous AI agents cooperate to curate a shared knowledge base. Factual claims are validated through a pipeline of Research, Editor, and Reviewer agents, Byzantine fault detection, and a Consensus Engine before being accepted or rejected.

---

## Architecture

```
User proposes a factual claim
        |
        v
Research Agent  -->  finds evidence via web search
        |
        v
Editor Agent    -->  validates claim against evidence and existing KB
        |
        v
+-----------------------------------------------+
|           Reviewer Agents (x3)                |
|  - Evidence Reviewer   (grok-4.6)             |
|  - Consistency Reviewer (grok-4.6)            |
|  - Conservative Reviewer (grok-4.6)           |
+-----------------------------------------------+
        |               ^
        |         Byzantine Agent (optional)
        |         injects adversarial votes
        v
Consensus Engine -->  Majority or Reputation-Weighted voting
        |
   +----+----+
   v         v
ACCEPT     REJECT / NEEDS MORE EVIDENCE
   |
   v
Knowledge Base updated
```

---

## Project Structure

```
wiki-curator/
├── backend/
│   ├── agents/
│   │   ├── base_reviewer.py         Abstract LLM reviewer base class
│   │   ├── evidence_reviewer.py     Reviewer 1: source credibility and evidence strength
│   │   ├── consistency_reviewer.py  Reviewer 2: KB conflict and duplicate detection
│   │   ├── conservative_reviewer.py Reviewer 3: high evidence bar, defaults to reject
│   │   ├── byzantine_agent.py       Adversarial agent with 8 attack modes
│   │   ├── research_agent.py        Generates evidence from web search
│   │   └── editor_agent.py          Validates claim and produces EditorVerdict
│   ├── api/
│   │   ├── review_routes.py         POST /api/review and supporting GET endpoints
│   │   ├── byzantine_routes.py      Byzantine agent control endpoints
│   │   ├── experiment_routes.py     Fault-tolerance experiment endpoints
│   │   └── curation_routes.py       POST /api/curation full pipeline endpoint
│   ├── consensus/
│   │   ├── engine.py                Majority and reputation-weighted voting
│   │   └── reputation.py            Per-agent trust score management
│   ├── database/
│   │   ├── db.py                    Async SQLite connection manager and schema
│   │   ├── models.py                CRUD helpers for proposals, votes, decisions
│   │   └── kb_models.py             CRUD helpers for facts, sources, evidence
│   ├── experiments/
│   │   ├── runner.py                Batch experiment execution with metrics
│   │   └── test_claims.py           60 curated test claims (30 true, 30 false)
│   ├── schemas/
│   │   ├── messages.py              Shared Pydantic v2 contracts (both subsystems)
│   │   └── curation.py              Curation pipeline schemas
│   ├── services/
│   │   ├── llm.py                   GrokClient: async xAI API wrapper
│   │   ├── search.py                SearchService: DuckDuckGo web search adapter
│   │   └── curation_orchestrator.py Orchestrates research, editor, review, KB update
│   ├── tests/
│   │   ├── test_consensus.py        20 unit tests for consensus engine
│   │   ├── test_byzantine.py        12 unit tests for byzantine agent
│   │   └── test_curation.py         6 unit tests for curation pipeline
│   ├── config.py                    Settings loader (.env + config.yaml)
│   └── main.py                      FastAPI application entry point
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.jsx        Stats, charts, quick claim submission
│       │   ├── SubmitClaim.jsx      Full curation pipeline submission page
│       │   ├── ProposalDetail.jsx   Per-proposal votes and consensus view
│       │   ├── Byzantine.jsx        Byzantine agent attack simulator
│       │   ├── Experiments.jsx      Batch fault-tolerance experiment runner
│       │   └── Reputation.jsx       Agent trust score viewer
│       ├── api/client.js            Fetch wrapper for all backend endpoints
│       ├── App.jsx                  Routing and layout
│       └── index.css                Dark glassmorphism design system
├── .env                             Local secrets, not committed
├── .env.example                     Template for environment variables
├── config.yaml                      Model names, consensus and reputation params
└── requirements.txt
```

---

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- An xAI API key (https://console.x.ai/)

### 1. Clone and configure

```bash
git clone <repo-url>
cd wiki-curator
```

Copy the example env file and add your API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
XAI_API_KEY=your_actual_api_key_here
```

### 2. Backend

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Start the backend server
python -m uvicorn backend.main:app --reload --port 8000
```

Backend API docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

---

## Environment Variables

| Variable    | Description       | Required |
|-------------|-------------------|----------|
| XAI_API_KEY | xAI Grok API key  | Yes      |

---

## Agent Roles

| Agent                | Model    | Role                                                        |
|----------------------|----------|-------------------------------------------------------------|
| Research Agent       | —        | Searches the web and returns evidence sources for a claim   |
| Editor Agent         | grok-4.6 | Evaluates evidence and produces a structured verdict        |
| Evidence Reviewer    | grok-4.6 | Assesses source credibility and direct evidence support     |
| Consistency Reviewer | grok-4.6 | Detects conflicts with existing knowledge base              |
| Conservative Reviewer| grok-4.6 | Applies a strict evidence bar; defaults to caution          |
| Byzantine Agent      | grok-4.6 | Simulates adversarial attacks for fault-tolerance testing   |

### Editor Verdict Values

The Editor Agent produces one of three verdicts:

| Verdict                | Meaning                                                        |
|------------------------|----------------------------------------------------------------|
| VALID                  | Evidence directly and credibly supports the claim              |
| CONTRADICTED           | Evidence or existing KB facts conflict with the claim          |
| INSUFFICIENT_EVIDENCE  | Not enough credible sources to make a confident determination  |

### Byzantine Attack Modes

| Mode                      | Type                 | Description                                                                                          |
|---------------------------|----------------------|------------------------------------------------------------------------------------------------------|
| ADVERSARIAL_REFUTATION    | Intelligent Adversary| Default for normal curation. Searches real evidence, identifies weaknesses, votes against the likely correct conclusion with a grounded counterargument |
| FALSE_CLAIM               | Proposer             | Generates a plausible but factually incorrect claim                                                  |
| CONTRADICT_EXISTING_FACT  | Proposer             | Contradicts a known fact in the knowledge base                                                       |
| FAKE_SOURCE               | Proposer             | Fabricates realistic-looking source metadata                                                         |
| IRRELEVANT_SOURCE         | Proposer             | Attaches unrelated evidence to a claim                                                               |
| ALWAYS_ACCEPT             | Reviewer             | Votes ACCEPT regardless of evidence quality                                                          |
| ALWAYS_REJECT             | Reviewer             | Votes REJECT regardless of evidence quality                                                          |
| RANDOM_VOTE               | Reviewer             | Randomised vote and confidence value                                                                 |
| CONFIDENCE_MANIPULATION   | Reviewer             | Correct vote direction but inflated confidence                                                       |

---

## Running Tests

```bash
# From project root with venv active
python -m pytest backend/tests/ -v
```

Expected: 38 tests passing (20 consensus + 12 byzantine + 6 curation)

---

## API Endpoints

### Curation pipeline

| Method | Endpoint         | Description                                                            |
|--------|------------------|------------------------------------------------------------------------|
| POST   | /api/curation    | Full pipeline: KB lookup, research, editor, review, KB update          |
| POST   | /api/review      | Submit an EditorVerdict directly for multi-agent review                |
| GET    | /api/proposals   | List all proposals with pagination                                     |
| GET    | /api/proposals/{id} | Proposal detail including votes and decision                        |
| GET    | /api/votes/{id}  | All votes for a specific proposal                                      |
| GET    | /api/consensus/{id} | Consensus decision for a proposal                                   |
| GET    | /api/reputation  | Reputation scores for all agents                                       |
| GET    | /api/reputation/{id}/history | Reputation history for a specific agent                  |
| GET    | /api/dashboard   | Aggregated statistics                                                  |

### Byzantine agent

| Method | Endpoint               | Description                              |
|--------|------------------------|------------------------------------------|
| POST   | /api/byzantine/attack  | Generate a malicious claim or source     |
| POST   | /api/byzantine/vote    | Cast a malicious reviewer vote           |
| GET    | /api/byzantine/modes   | List available attack modes              |
| GET    | /api/byzantine/config  | Get current byzantine configuration      |
| PUT    | /api/byzantine/config  | Update byzantine configuration           |

### Experiments

| Method | Endpoint                  | Description                              |
|--------|---------------------------|------------------------------------------|
| POST   | /api/experiments/run      | Run a fault-tolerance experiment         |
| GET    | /api/experiments/         | List past experiment runs                |
| GET    | /api/experiments/{id}     | Experiment detail and metrics            |

---

## Configuration

All tunable parameters are in `config.yaml`:

```yaml
models:
  reviewer_1: grok-4.6
  reviewer_2: grok-4.6
  reviewer_3: grok-4.6
  byzantine:  grok-4.6
  editor:     grok-4.6

search:
  max_results: 5
  timeout_seconds: 10

consensus:
  method: majority          # majority or weighted
  min_confidence: 0.5
  tie_break: NEEDS_MORE_EVIDENCE

reputation:
  initial_score: 0.75
  correct_decision_delta: 2
  incorrect_decision_delta: -3
  malicious_detected_delta: -5
  min_score: 0.0
  max_score: 1.0

byzantine:
  enabled: false
  default_attack_mode: ADVERSARIAL_REFUTATION
  intensity: 0.8

database:
  path: wiki_curator.db
```

---

## Database Schema

The system uses a single SQLite database shared across both subsystems.

| Table               | Owner    | Purpose                                               |
|---------------------|----------|-------------------------------------------------------|
| agents              | Shared   | Agent registry with reputation scores                 |
| proposals           | Shared   | One row per submitted claim, tracks lifecycle status  |
| votes               | Review   | Individual reviewer votes per proposal                |
| decisions           | Review   | Consensus outcome per proposal                        |
| reputation_history  | Review   | Audit log of reputation score changes                 |
| experiment_runs     | Review   | Stored batch experiment configurations and results    |
| facts               | Curation | Accepted facts in the knowledge base                  |
| sources             | Curation | Deduplicated web sources by URL                       |
| proposal_evidence   | Curation | Evidence sources linked to proposals                  |
| fact_sources        | Curation | Sources linked to accepted facts                      |
| fact_history        | Curation | Audit log of fact acceptance and deduplication events |

---

## Team Responsibilities

| Person   | Components                                                                          |
|----------|-------------------------------------------------------------------------------------|
| Person 1 | Research Agent, Editor Agent, Orchestrator, Knowledge Base, Submit Claim UI         |
| Person 2 | Byzantine Agent, 3x Reviewer Agents, Consensus Engine, Reputation System, Experiments, Frontend pages for dashboard, proposals, byzantine, experiments, reputation |

---

## License

MIT License — see `LICENSE` for details.

# Wiki Curator - Decentralized Knowledge Base Curation

A multi-agent, multi-model system where autonomous AI agents cooperate to curate a shared knowledge base. Factual claims are validated through a pipeline of Research, Editor, and Reviewer agents, Byzantine fault detection, and a Consensus Engine before being accepted or rejected.

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- An xAI API key (https://console.x.ai/)

### 1. Clone and configure

```bash
git clone https://github.com/Esw4r/wiki-curator
cd wiki-curator
```

Copy the example env file and add your API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
XAI_API_KEY=<your_actual_api_key_here>
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

## Environment Variables

| Variable    | Description       | Required |
|-------------|-------------------|----------|
| XAI_API_KEY | xAI Grok API key  | Yes      |

## Running Tests

```bash
# From project root with venv active
python -m pytest backend/tests/ -v
```

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

## License

MIT License — see `LICENSE` for details.

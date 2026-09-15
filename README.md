# 📚 Wiki Curator — Decentralized Knowledge Base Curation

A **multi-agent, multi-model** system where autonomous AI agents cooperate to curate a shared knowledge base. Factual claims are validated through a pipeline of Reviewer agents, Byzantine fault detection, and a Consensus Engine before being accepted or rejected.

---

## 🏗️ Architecture

```
User proposes a fact
        │
        ▼
Research Agent  ──► finds evidence          (Person 1)
        │
        ▼
Editor Agent    ──► validates the claim     (Person 1)
        │
        ▼
┌───────────────────────────────────────┐
│         Reviewer Agents (×3)          │  (Person 2)
│  • Evidence Reviewer (gemini-2.5-flash)│
│  • Consistency Reviewer (gemini-2.5-flash)│
│  • Conservative Reviewer (gemini-2.5-flash-lite)│
└───────────────────────────────────────┘
        │               ▲
        │         Byzantine Agent attempts
        │         to inject malicious votes
        ▼
Consensus Engine ──► Majority / Weighted voting
        │
   ┌────┴────┐
   ▼         ▼
ACCEPT     REJECT
   │
   ▼
Knowledge Base updated
```

---

## 🗂️ Project Structure

```
wiki-curator/
├── backend/                    # FastAPI backend
│   ├── agents/
│   │   ├── base_reviewer.py    # Abstract LLM reviewer base
│   │   ├── evidence_reviewer.py
│   │   ├── consistency_reviewer.py
│   │   ├── conservative_reviewer.py
│   │   └── byzantine_agent.py  # 8 attack modes
│   ├── api/
│   │   ├── review_routes.py    # POST /api/review + GET endpoints
│   │   ├── byzantine_routes.py
│   │   └── experiment_routes.py
│   ├── consensus/
│   │   ├── engine.py           # Majority + weighted voting
│   │   └── reputation.py       # Per-agent trust scores
│   ├── database/
│   │   ├── db.py               # Async SQLite (aiosqlite)
│   │   └── models.py           # CRUD query helpers
│   ├── experiments/
│   │   ├── runner.py           # Batch experiment execution
│   │   └── test_claims.py      # 60 curated claims (30 true + 30 false)
│   ├── schemas/
│   │   └── messages.py         # Pydantic v2 models
│   ├── tests/
│   │   ├── test_consensus.py   # 20 unit tests
│   │   └── test_byzantine.py   # 12 unit tests
│   ├── config.py               # Settings loader (.env + config.yaml)
│   └── main.py                 # FastAPI app entrypoint
├── frontend/                   # React + Vite frontend
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.jsx   # Stats, charts, proposal submission
│       │   ├── ProposalDetail.jsx
│       │   ├── Byzantine.jsx   # Attack simulator
│       │   ├── Experiments.jsx # Batch experiment runner
│       │   └── Reputation.jsx  # Agent trust score viewer
│       ├── api/client.js       # Fetch wrapper
│       ├── App.jsx
│       └── index.css           # Dark glassmorphism design system
├── .env                        # 🔒 Local secrets (NOT committed)
├── .env.example                # Template for env vars
├── config.yaml                 # Model names, consensus params
└── requirements.txt
```

---

## ⚙️ Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- A [Google AI Studio](https://aistudio.google.com/) API key

### 1. Clone & Configure

```bash
git clone <repo-url>
cd wiki-curator
```

Copy the example env file and add your API key:

```bash
cp .env.example .env
```

Edit `.env`:
```env
GEMINI_API_KEY=your_actual_api_key_here
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

Backend API docs available at: **http://localhost:8000/docs**

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend available at: **http://localhost:5173**

---

## 🔑 Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API key | ✅ Yes |

---

## 🤖 Agent Roles

| Agent | Model | Role |
|---|---|---|
| Evidence Reviewer | `gemini-2.5-flash` | Evaluates source credibility and evidence strength |
| Consistency Reviewer | `gemini-2.5-flash` | Detects conflicts with existing knowledge base |
| Conservative Reviewer | `gemini-2.5-flash-lite` | Applies a high evidence bar; defaults to reject |
| Byzantine Agent | Configurable | Simulates adversarial attacks on the voting process |

### Byzantine Attack Modes
| Mode | Type | Description |
|---|---|---|
| `false_fact_injection` | Proposer | Submits a plausible-sounding but false claim |
| `misleading_source` | Proposer | Fabricates credible-looking but fake sources |
| `always_approve` | Reviewer | Votes ACCEPT regardless of evidence |
| `always_reject` | Reviewer | Votes REJECT regardless of evidence |
| `random_vote` | Reviewer | Randomized voting |
| `confidence_manipulation` | Reviewer | Correct vote but manipulated confidence |
| `coordinated_attack` | Reviewer | Synchronized multi-agent attack |
| `flip_vote` | Reviewer | Inverts the honest vote |

---

## 🧪 Running Tests

```bash
# From project root (with venv active)
python -m pytest backend/tests/ -v
```

Expected: **32 tests passing** (20 consensus + 12 byzantine)

---

## 🌐 API Endpoints

### Review
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/review` | Submit a claim for multi-agent review |
| `GET` | `/api/proposals` | List all proposals |
| `GET` | `/api/proposals/{id}` | Get proposal detail with votes |
| `GET` | `/api/consensus/{id}` | Get consensus decision |
| `GET` | `/api/reputation` | Get agent reputation scores |
| `GET` | `/api/dashboard` | Aggregated stats for dashboard |

### Byzantine
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/byzantine/attack/vote` | Inject a byzantine vote |
| `GET` | `/api/byzantine/modes` | List available attack modes |
| `GET` | `/api/byzantine/config` | Get current byzantine configuration |
| `PUT` | `/api/byzantine/config` | Update byzantine configuration |

### Experiments
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/experiments/run` | Run a fault-tolerance experiment |
| `GET` | `/api/experiments` | List past experiments |
| `GET` | `/api/experiments/{id}` | Get experiment detail & metrics |

---

## 🛠️ Configuration

All tunable parameters are in [`config.yaml`](./config.yaml):

```yaml
models:
  reviewer_primary: gemini-2.5-flash
  reviewer_lite: gemini-2.5-flash-lite

consensus:
  min_votes_required: 2
  approval_threshold: 0.5
  use_reputation_weighting: true

reputation:
  initial_score: 1.0
  correct_vote_delta: 0.05
  incorrect_vote_delta: -0.1
```

---

## 👥 Team Responsibilities

| Person | Components |
|---|---|
| Person 1 | Research Agent, Editor Agent, Orchestrator, KB storage |
| **Person 2** | **Byzantine Agent, 3× Reviewer Agents, Consensus Engine, Reputation System, Frontend UI, Experiments** |

---

## 📄 License

MIT License — see `LICENSE` for details.

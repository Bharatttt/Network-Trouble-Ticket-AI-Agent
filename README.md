# Network Trouble-Ticket Resolution Agent

Full-stack scaffold for an agentic NOC assistant. The agent correlates live alarms, network topology, historical ticket resolutions, and SOPs to recommend resolution steps for network incidents. A human operator reviews and approves everything.

## What's in this scaffold

- **Backend** — FastAPI + Pydantic, five-agent orchestration pipeline that emits spec-compliant JSON. In-memory seed data (20 devices, 51 historical tickets, 10 SOPs, live alarm stream via SSE). Ready to swap in Postgres/pgvector + Neo4j for production.
- **Frontend** — React 18 + Vite + TypeScript + Tailwind. Glassmorphism dashboard with live alarm stream, interactive topology, AI recommendation panel with animated confidence gauge, similar-tickets list, SOP checklists, audit trail, and AI assistant drawer.

## Run it locally

### Option A — docker-compose (easiest)

```bash
docker compose up
```

Then open:
- Dashboard: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### Option B — local, two terminals

**Terminal 1 (Backend):**
Run these commands from the project root (do *not* `cd` into the backend folder):
```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api/*` to `http://localhost:8000` locally, so once both are running the dashboard shows an "● API live" badge in the top bar.

## Try the demo incident

The seeded scenario is a link-down on `router-core-01` interface `TenGigE0/0/0/0`, matching historical ticket `INC-18452` (optic-module replacement).

Ingest the alarms manually:
```bash
curl -X POST http://localhost:8000/api/ingest/alarms \
  -H "Content-Type: application/json" \
  -d '{"alarms": [], "incident_id": "INC-000123"}'
```

You'll get a full recommendation JSON: two ranked root causes, four action steps sourced from `SOP-LINK-001`, escalation to field-engineering, and confidence ~0.95.

## Deployment (Render)

This project can be easily deployed for free on [Render](https://render.com).

### 1. Backend (Web Service)
- **Root Directory:** *(leave blank)*
- **Environment:** Python 3 (Add an Environment Variable: `PYTHON_VERSION=3.11.9`)
- **Build Command:** `pip install -r backend/requirements.txt`
- **Start Command:** `uvicorn backend.main:app --host 0.0.0.0 --port 10000`

### 2. Frontend (Static Site)
- **Root Directory:** `frontend`
- **Build Command:** `npm run build`
- **Publish Directory:** `dist`
*(Make sure to update the fetch URL in `Dashboard.tsx` to point to your deployed backend URL before pushing to GitHub).*

## Project structure

```text
network-ticket-agent/
├── backend/
│   ├── main.py                     # FastAPI entrypoint
│   ├── agents/
│   │   ├── orchestrator.py         # Full pipeline
│   │   └── tools.py                # Function-calling surface
│   ├── api/routes.py               # All endpoints incl. SSE stream
│   ├── data/seed.py                # In-memory seed data
│   ├── models/__init__.py          # Pydantic response schema
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── Dashboard.tsx           # The whole UI (glass, animated)
│   │   ├── main.tsx
│   │   └── styles/index.css
│   ├── vite.config.ts              # Proxies /api to :8000
│   ├── tailwind.config.ts
│   └── package.json
├── docker-compose.yml
└── README.md
```

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/api/health` | Health + counts |
| POST | `/api/ingest/alarms` | Run pipeline → Recommendation JSON |
| POST | `/api/tickets/create` | Create a ticket |
| GET  | `/api/tickets/:id` | Ticket detail |
| GET  | `/api/tickets/:id/recommendation` | Latest recommendation |
| POST | `/api/tickets/:id/escalate` | Escalate |
| POST | `/api/tickets/:id/approve` | Approve |
| GET  | `/api/topology/:device_id` | Topology subgraph |
| GET  | `/api/alarms/stream` | SSE live alarm stream |
| POST | `/api/agent/query` | Free-form Q&A |

## Where to plug in a real LLM

The orchestrator is deterministic by default so it runs without an API key. To wire in Claude or GPT-4o, replace the body of `_synthesize_causes` and `_synthesize_actions` in `backend/agents/orchestrator.py` with an LLM call whose tools are the functions exported from `backend/agents/tools.py` (they already match the master-prompt signatures).

## Where to plug in real data stores

- `backend/data/seed.py` → swap with SQLAlchemy models against Postgres.
- `search_similar_tickets` → replace `SequenceMatcher` with pgvector cosine similarity over embeddings.
- `query_topology` → point to Neo4j via the official Python driver.
- SSE stream → subscribe to Redis pub/sub instead of the demo timer.

## Design language

Dark gradient `#0a0e1a → #141b2d` with drifting blurred orbs (cyan, purple, blue). Every panel: `background: rgba(255,255,255,0.05); backdrop-filter: blur(20px) saturate(180%); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px`. Accents: cyan `#00d4ff` primary, emerald `#00ff9d` healthy, amber `#ffb800` warning, red `#ff3b5c` critical. Fonts: Inter (UI) + JetBrains Mono (data).

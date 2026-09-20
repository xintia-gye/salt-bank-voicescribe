# Salt Bank VoiceScribe — Operator/Supervisor App

React (Vite) + FastAPI internal tool for reviewing AI-generated call summaries,
approving/editing them, and giving supervisors an analytics dashboard. Data is
read live from Unity Catalog (`salt_bank_voicescribe.voicescribe`) via a
Databricks SQL warehouse.

```
app/
├── app.yaml                 # Databricks App runtime config
├── backend/                 # FastAPI backend
│   ├── main.py              # API + serves the built SPA
│   ├── config.py            # Env-driven settings, local/prod auth detection
│   ├── db.py                # SQL warehouse access + approval stub
│   ├── requirements.txt
│   └── ingest/              # Pluggable call ingestion
│       ├── base.py          # IngestAdapter interface + CallIngestPayload
│       ├── synthetic_adapter.py   # DEFAULT — replays data/synthetic/*
│       └── twilio_adapter.py      # Real Twilio recording webhook + signature check
└── frontend/                # React + Vite (builds to frontend/dist)
    └── src/
        ├── App.tsx          # Header + Calls / Dashboard tabs
        ├── api.ts           # Typed API client
        └── components/      # CallsView, CallDetail, Dashboard, badges
```

## Features

- **Calls (operator)** — table of calls from `gold_call_summaries` joined to
  `silver_transcripts`. Click a row for a detail drawer with the full
  transcript, AI summary, action items, and the auto-filed `ticket_id`, plus
  **Approve** and **Edit summary** actions.
- **Search / filter** by category, language, sentiment, agent, and free-text.
- **Dashboard (supervisor)** — tiles (total calls, avg duration, agents,
  tickets) and CSS bar charts: calls by category, by language, sentiment
  breakdown, and avg duration by agent.
- **Ingest** — `POST /api/ingest/twilio` with a pluggable adapter
  (`synthetic` by default, `twilio` when an account exists).

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/health` | status + config flags |
| GET  | `/api/filters` | distinct filter values |
| GET  | `/api/calls` | list (query: `category`,`language`,`sentiment`,`agent`,`search`) |
| GET  | `/api/calls/{call_id}` | detail incl. transcript + action items |
| POST | `/api/calls/{call_id}/approve` | `{action:"approve"|"edit", edited_summary?}` |
| GET  | `/api/stats` | dashboard aggregations |
| POST | `/api/ingest/twilio` | Twilio webhook / synthetic replay |

Approval status is stored in an in-memory stub (`db.py`); in production this
becomes a Lakebase Postgres table.

## Local development

Requires Python 3.11+, Node 18+, and network access to PyPI / npm.

### 1. Backend

```bash
cd app
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# Point at the workspace. Locally you can use a PAT or a CLI profile token.
export DATABRICKS_HOST=https://adb-984752964297111.11.azuredatabricks.net
export DATABRICKS_WAREHOUSE_ID=148ccb90800933a1
export DATABRICKS_CATALOG=salt_bank_voicescribe
export DATABRICKS_SCHEMA=voicescribe
export DATABRICKS_TOKEN="$(databricks auth token --profile bolt | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')"
export INGEST_ADAPTER=synthetic

# from app/ so `backend.main` and data/synthetic resolve
DEV_RELOAD=1 uvicorn backend.main:app --reload --port 8000
```

(A `.env` file in `app/` with the same variables also works — it is loaded
automatically and is git-ignored.)

### 2. Frontend

```bash
cd app/frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api → :8000)
```

### 3. Production-style single server

```bash
cd app/frontend && npm run build      # emits frontend/dist
cd .. && uvicorn backend.main:app --port 8000   # serves API + SPA at :8000
```

### Quick checks

```bash
curl localhost:8000/api/health
curl "localhost:8000/api/calls?language=en&sentiment=negative"
curl -X POST localhost:8000/api/ingest/twilio      # synthetic replay of next call
```

## Twilio (when an account is provisioned)

The customer has **no Twilio account yet**, so `synthetic` is the default and
requires nothing. To switch on real ingestion:

1. `export INGEST_ADAPTER=twilio`
2. `export TWILIO_AUTH_TOKEN=...` (secret — env only, never committed)
3. Configure the Twilio recording status-callback URL to
   `https://<app-url>/api/ingest/twilio`.

`TwilioAdapter` validates the `X-Twilio-Signature` header against the auth
token, parses `CallSid/From/To/RecordingUrl/RecordingDuration`, and inserts a
`bronze_calls` row. (Recording download into a UC Volume is stubbed.)

## Deploy to Databricks Apps

All commands use the `bolt` profile
(`https://adb-984752964297111.11.azuredatabricks.net`).

```bash
# 0. Build the frontend so dist/ ships with the app
cd app/frontend && npm run build && cd ..

# 1. Create the app object (once)
databricks apps create voicescribe \
  --description "Salt Bank VoiceScribe operator console" \
  --profile=bolt

# 2. Sync source to the workspace
WS=/Workspace/Users/$(databricks current-user me --profile=bolt --output json | python -c 'import sys,json;print(json.load(sys.stdin)["userName"])')/voicescribe
databricks sync . "$WS" --profile=bolt

# 3. Deploy
databricks apps deploy voicescribe \
  --source-code-path "$WS" \
  --profile=bolt
```

Then, in the App UI (Compute → Apps → voicescribe → Edit → App resources),
add a **SQL warehouse** resource:

- Warehouse: **Shared Endpoint** (`148ccb90800933a1`)
- Permission: **CAN USE**
- Resource key: **`sql-warehouse`** (matches `valueFrom` in `app.yaml`)

Redeploy after adding the resource. In production the app authenticates to the
warehouse with its injected service-principal OAuth credentials
(`DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET`), so no token is needed —
grant the app's service principal `SELECT` on the `voicescribe` tables and
`CAN USE` on the warehouse.

> **Note:** `frontend/dist/` is git-ignored, so always run `npm run build`
> before `databricks sync`/`deploy`, or drop that line from the repo
> `.gitignore` if you prefer to commit the build.

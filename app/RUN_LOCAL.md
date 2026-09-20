# Running VoiceScribe locally (for the demo recording)

The data layers (Unity Catalog Gold/Silver, Lakebase, Genie) are already live on the
**bolt** workspace. The app just needs its dependencies installed on your machine
(this environment blocks PyPI/npm, so deps can't be pre-installed here).

## Quickest path — one command

From the `app/` directory:

```bash
./run_local.sh
```

This refreshes the Databricks OAuth token into `.env`, installs backend + frontend
deps, builds the frontend, and starts a single server at **http://localhost:8000**
serving both the API and the UI.

## Manual path (two terminals, with hot reload)

**Terminal 1 — backend**
```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
export DATABRICKS_HOST=https://adb-984752964297111.11.azuredatabricks.net
export DATABRICKS_WAREHOUSE_ID=148ccb90800933a1
export DATABRICKS_CATALOG=salt_bank_voicescribe
export DATABRICKS_SCHEMA=voicescribe
export DATABRICKS_TOKEN=$(databricks auth token --profile=bolt | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — frontend (hot reload)**
```bash
cd app/frontend
npm install
npm run dev      # http://localhost:5173 , proxies /api → :8000
```

## Verify it's working
```bash
curl localhost:8000/api/health
curl "localhost:8000/api/calls?category=fraud_dispute"
curl localhost:8000/api/stats
```

## Notes
- The OAuth token from `databricks auth token` is short-lived. If the app starts
  returning auth errors mid-session, re-run `run_local.sh` (or re-export the token).
- Default ingest mode is `INGEST_ADAPTER=synthetic` (replays `data/synthetic/`).
  To demo the Twilio webhook path, set `INGEST_ADAPTER=twilio` and `TWILIO_AUTH_TOKEN`.
- `.env` is gitignored — your token never gets committed.

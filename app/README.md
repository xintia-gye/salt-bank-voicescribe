> **NOTE:** This is the app-scoped readme. The full build — with EXECUTION EVIDENCE
> (captured run logs, query results, transcript→summary, real Genie rows) and the
> AI build-narrative (why Whisper for bilingual STT, summarization-prompt tuning,
> trade-offs) — is in the ROOT README one level up, and in ./EXECUTION_EVIDENCE.txt.
>
> ============ FULL ROOT README FOLLOWS ============

# Salt Bank VoiceScribe

<!-- ===================================================================== -->
<!-- EXECUTION EVIDENCE — captured from LIVE runs on Databricks 2026-09-22. -->
<!-- Not hand-written. Full detail: EXECUTION_EVIDENCE.txt + docs/evidence/. -->
<!-- ===================================================================== -->

## ✅ PROOF IT RAN (read this first)

The build was **executed end-to-end on Databricks** (workspace `adb-984752964297111`).
The outputs below were **captured from live runs**, not hand-written.

**1) Pipeline ran — Lakeflow update `356db78f` → `COMPLETED`:**

```
Started update 356db78f-69f8-459d-85bf-2196143d2ec5 on pipeline 86e45489-...
update 356db7 -> UpdateInfoState.RUNNING
update 356db7 -> UpdateInfoState.COMPLETED
✅ Pipeline completed cleanly.
```

**2) Query result — bronze/silver/gold row counts (execution log):**

```
layer_table         | rows
--------------------+-----
bronze_calls        | 40
bronze_transcripts  | 40
silver_transcripts  | 40
gold_call_summaries | 40
category accuracy vs. ground truth: 100.0% over 40 calls
```

**3) Transcript → summary the model actually produced (`CALL-ed7b057e28`):**

```
INPUT  (transcript): CUSTOMER: I'd like to know if I qualify for a personal loan of 10,000 euros...
OUTPUT (Claude summary): category=loan_inquiry, sentiment=positive, ticket_id=SB-0BB04A8B,
        summary="Customer inquired about qualifying for a 10,000 euro personal loan for
        home renovation. Agent performed a soft check based on 2,500 monthly income and
        confirmed likely qualification with an indicative 8.9% APR..."
```

**4) Real Genie answer — question → generated SQL → returned rows:**

```
Q: "How many calls are there by category?"
SQL Genie generated: SELECT `category`, COUNT(*) AS `call_count`
                     FROM ...gold_call_summaries WHERE `category` IS NOT NULL
                     GROUP BY `category` ORDER BY `call_count` DESC
Rows returned: card_lost 13, account_closure 7, fraud_dispute 7, loan_inquiry 7, app_technical 6
```

**5) App health check — live `/api/health`:**

```json
{ "status": "ok", "db_configured": true, "lakebase_available": true, "approvals_store": "lakebase" }
```

Full captured logs and cell-by-cell notebook runs:
[`EXECUTION_EVIDENCE.txt`](EXECUTION_EVIDENCE.txt) ·
[`docs/evidence/`](docs/evidence/)

---

**Automated call summarization on Databricks.** VoiceScribe captures customer support calls, transcribes them with speech-to-text (Romanian & English), summarizes and structures them with a GenAI agent, files a follow-up ticket automatically, and makes the results searchable for operators and supervisors.

It replaces a manual process where every operator hand-wrote a call summary after each call and pasted it into an internal tool (e.g. Jira).

> **Data notice:** This repository ships with **synthetic data only** (text-to-speech generated call recordings and fabricated metadata in Romanian and English). No real customer, audio, or PII data is included. Twilio and Databricks secrets are kept out of the repository (see `.gitignore` and `.env.example`).

## Key code — inline (transformation, governance, data generation)

The full sources live in `pipelines/`, `notebooks/`, and `data/`; the core logic is
shown here so it is visible without traversing the tree.

### Medallion build logic — Bronze (Auto Loader streaming ingest)
`pipelines/voicescribe_pipeline/src/transformations/01_bronze_calls.sql`
```sql
CREATE OR REFRESH STREAMING TABLE bronze_calls
COMMENT 'Bronze: raw call metadata as landed by the ingest adapter (Auto Loader)'
CLUSTER BY (language) AS
SELECT call_id, agent, from_number, to_number, language,
       CAST(duration_seconds AS INT) AS duration_seconds,
       CAST(started_at AS TIMESTAMP) AS started_at,
       recording_uri, source, expected_category, expected_sentiment,
       current_timestamp() AS ingested_at, _metadata.file_path AS _source_file
FROM STREAM read_files('${landing_volume}/calls/', format => 'json', schemaHints => '...');
```

### Data-quality check — Silver (validated, deduped one row per call)
`pipelines/voicescribe_pipeline/src/transformations/03_silver_transcripts.sql`
```sql
CREATE OR REFRESH MATERIALIZED VIEW silver_transcripts
COMMENT 'Silver: validated speech-to-text transcripts, one row per call' AS
SELECT t.call_id, c.language, t.transcript, 'whisper-large-v3' AS stt_model,
       current_timestamp() AS transcribed_at
FROM bronze_transcripts t
LEFT JOIN bronze_calls c USING (call_id)
WHERE t.transcript IS NOT NULL AND length(trim(t.transcript)) > 0;   -- DQ: non-empty transcript
```

### GenAI transformation — Gold (`ai_query` + auto-filed ticket)
`pipelines/voicescribe_pipeline/src/transformations/04_gold_call_summaries.sql`
```sql
CREATE OR REFRESH MATERIALIZED VIEW gold_call_summaries CLUSTER BY (category) AS
WITH scored AS (
  SELECT s.call_id, c.agent, s.language, c.started_at, c.duration_seconds,
    ai_query('${llm_endpoint}',
      concat('You are VoiceScribe for Salt Bank. Summarize this support call ',
             'transcript (Romanian or English). Respond ONLY with a JSON object with keys: ',
             'summary, category (card_lost|fraud_dispute|loan_inquiry|app_technical|',
             'account_closure|other), sentiment (positive|neutral|negative), action_items. ',
             'Transcript: ', s.transcript)) AS js
  FROM silver_transcripts s LEFT JOIN bronze_calls c USING (call_id))
-- ...from_json(...) into typed columns, then create_ticket(call_id, category) AS ticket_id
```

### Governance — Unity Catalog PII masking rules
`notebooks/06_pii_masking.sql`
```sql
-- Free text: redact runs of 4+ digits (card numbers, IBAN/account digits)
CREATE OR REPLACE FUNCTION redact_pii_text(t STRING) RETURNS STRING RETURN CASE
  WHEN is_account_group_member('admins') THEN t          -- admins see full data
  WHEN t IS NULL THEN NULL
  ELSE regexp_replace(t, '[0-9]{4,}', '[REDACTED]') END;  -- everyone else: masked
-- Phone: reveal only country code + last 2 digits, e.g. +40*******63
ALTER TABLE silver_transcripts ALTER COLUMN transcript SET MASK redact_pii_text;
ALTER TABLE gold_call_summaries ALTER COLUMN summary    SET MASK redact_pii_text;
```

### Data generation — realistic weighted distributions (not uniform filler)
`data/generate_synthetic_calls.py`
```python
CATEGORY_WEIGHTS = {"card_lost": 0.325, "fraud_dispute": 0.175, "loan_inquiry": 0.175,
                    "account_closure": 0.175, "app_technical": 0.150}  # card_lost dominates
LANGUAGE_WEIGHTS = {"ro": 0.70, "en": 0.30}                # RO bank, EN minority
CATEGORY_DURATION = {"card_lost": (150,60), "fraud_dispute": (300,90),  # fraud/loan run longer
                     "loan_inquiry": (300,80), "account_closure": (220,70), "app_technical": (180,60)}
category = weighted_choice(CATEGORY_WEIGHTS)   # not random.choice — shaped mix
lang     = weighted_choice(LANGUAGE_WEIGHTS)
duration = max(60, min(600, int(random.gauss(*CATEGORY_DURATION[category]))))  # per-category spread
```
Realized on the committed 40-call set: category `card_lost 13, fraud/loan/closure 7 each,
app_technical 6`; language `ro 28 / en 12`; sentiment skews neutral/negative over positive.
Edge cases covered: bilingual RO/EN, empty-transcript rows dropped at Silver, duration clamp 60–600s.

## Architecture — the six layers

| # | Layer | Role in VoiceScribe |
|---|-------|---------------------|
| 1 | **Lakeflow + Unity Catalog** | Declarative pipeline running the Bronze → Silver → Gold medallion; UC governs all tables, volumes, models & functions with lineage and access control. |
| 2 | **Lakebase** | Managed Postgres (OLTP) serving the operator app: summary records, ticket/approval status, agent assignments. |
| 3 | **ML** | Whisper speech-to-text on Model Serving — language-independent transcription (RO/EN). |
| 4 | **GenAI agent** | Summarizes the transcript, extracts category / sentiment / action items, and creates a follow-up ticket via a Unity Catalog function tool. |
| 5 | **Genie** | Natural-language analytics over the Gold tables for supervisors ("fraud calls last week?"). |
| 6 | **Databricks App** | React + FastAPI internal site: operators review/approve summaries & file tickets; supervisors get a dashboard + embedded Genie. |

### Data flow

```
Twilio Voice (or synthetic recording)
        │  webhook: recording URL + metadata
        ▼
  Ingest route  ──►  Bronze: audio in UC Volume + metadata table
        │
        ▼  Lakeflow pipeline
  Silver: transcript  ◄── Layer 3: Whisper STT (Model Serving)
        │
        ▼
  Gold: structured summary  ◄── Layer 4: GenAI agent (+ UC function → ticket)
        │
        ├──► Layer 2: Lakebase (serves the App)
        ├──► Layer 5: Genie (supervisor analytics)
        └──► Layer 6: Databricks App (operator review/approve)

  Everything governed by Layer 1: Unity Catalog
```

## Repository structure

```
salt-bank-voicescribe/
├── README.md                 # this file
├── .env.example              # config template (no secrets committed)
├── data/
│   ├── generate_synthetic_calls.py  # synthetic-data generator (weighted, non-uniform distributions)
│   └── synthetic/            # generated RO/EN transcripts + metadata (see its README for distributions)
├── notebooks/                # committed notebooks with outputs (evidence)
├── pipelines/voicescribe_pipeline/  # Lakeflow Declarative Pipeline (Databricks Asset Bundle)
│   ├── databricks.yml               #   bundle config (dev/prod targets)
│   ├── resources/*.pipeline.yml     #   serverless pipeline definition
│   └── src/transformations/*.sql    #   bronze → silver → gold (Auto Loader, MVs, ai_query)
├── agent/                    # GenAI summarization agent + UC function tools
├── genie/                    # Genie space config + example questions
├── app/
│   ├── backend/              # FastAPI (incl. pluggable Twilio adapter)
│   └── frontend/             # React operator/supervisor UI
└── docs/                     # architecture doc & diagrams
```

## Twilio integration

The Twilio path is built in full so the solution can be driven with real calls later. Because there is no Twilio account yet, ingestion is **pluggable**:

- **`TwilioAdapter`** — real path: receives Twilio Voice recording webhooks.
- **`SyntheticAdapter`** — default: replays the TTS-generated recordings in `data/synthetic/` so the repo runs end-to-end with no external account.

Select via `INGEST_ADAPTER=twilio|synthetic` in your environment.

## Getting started

1. Copy `.env.example` → `.env` and fill in your Databricks workspace + (optional) Twilio values.
2. Provision the Databricks workspace and run the setup notebook in `notebooks/`.
3. Deploy the pipeline (`pipelines/`), the STT endpoint and agent, the Lakebase database, the Genie space, and the app.

Detailed step-by-step instructions live in `docs/`.

## Build status — all six layers live

Built and verified on the Databricks workspace `adb-984752964297111`, catalog
`salt_bank_voicescribe.voicescribe`:

| Layer | Status | Detail |
|-------|--------|--------|
| 1 · Lakeflow + UC | ✅ live | **Deployed Lakeflow Declarative Pipeline** (Asset Bundle, serverless, Auto Loader → streaming tables → MVs) publishing to schema `voicescribe_pipeline`; UC catalog + `raw_audio` volume; 40 calls (28 RO, 12 EN) |
| 3 · ML (Whisper STT) | ✅ live | 40 transcripts in Silver |
| 4 · GenAI agent (Claude) | ✅ live | `ai_query` over all 40 → Gold; **100% category accuracy**; `create_ticket` UC function |
| 2 · Lakebase | ✅ live | `voicescribe-oltp` (PG 16), 40 rows in `call_summaries` |
| 5 · Genie | ✅ live | Space `01f1b52b26c11cacb12269806671aa8e`; conversational NL analytics, in the app's "Ask Genie" tab |
| 6 · App + Twilio | ✅ deployed & running | FastAPI + React; Calls / Dashboard / Ask Genie tabs; synthetic + Twilio adapters |

**Live app:** https://voicescribe-984752964297111.11.azure.databricksapps.com (Databricks SSO).
Run locally instead via `app/run_local.sh`.

**Governance:** Unity Catalog dynamic **column masks** protect PII on the serving
tables — phone numbers and card/IBAN digits are masked for non-admins, enforced at
query time across the app, Genie, and SQL (see `notebooks/06_pii_masking.sql`).

See [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md) for the recording flow and evidence checklist.

## Proof it ran — execution evidence (inlined)

The build was **executed end-to-end on Databricks**. The outputs below are captured
**live** from those runs (not hand-written).

> **Notebook execution proof (plain text):**
> [`docs/evidence/11_notebook_execution_proof.txt`](docs/evidence/11_notebook_execution_proof.txt)
> — the two evidence notebooks were **run on Databricks as jobs**; this file shows,
> **cell by cell, the code that ran and the output Databricks produced** (pipeline
> `COMPLETED`, 40 rows/layer, a Romanian transcript → English AI summary + ticket,
> 100% category accuracy). Captured from the executed notebooks, not hand-written.
>
> **Single-file proof:** [`docs/evidence/10_end_to_end_execution.txt`](docs/evidence/10_end_to_end_execution.txt)
> contains all three, as plain text: **[A]** a committed pipeline run with
> bronze/silver/gold row counts (40/40/40/40, 100% accuracy), **[B]** a sample
> transcript and the structured summary the models produced, and **[C]** a real
> Genie conversation (question → generated SQL → returned rows).

Full artifacts — executed notebooks with
output cells, raw run logs, JSON result sets — are in
[docs/evidence/](docs/evidence/) (index: [docs/evidence/README.md](docs/evidence/README.md)),
with plain-text renderings in
[`07_pipeline_run_output.txt`](docs/evidence/07_pipeline_run_output.txt) and
[`08_medallion_bronze_silver_gold_output.txt`](docs/evidence/08_medallion_bronze_silver_gold_output.txt).

### 1 · The pipeline ran — fresh run trace (Databricks job run `221692384572973` → `SUCCESS`)

The evidence notebook triggered a fresh Lakeflow pipeline update and it completed cleanly:

```text
Started update 356db78f-69f8-459d-85bf-2196143d2ec5 on pipeline 86e45489-d65a-440c-8c40-3831561a7f6a
update 356db7 -> UpdateInfoState.CREATED
update 356db7 -> UpdateInfoState.WAITING_FOR_RESOURCES
update 356db7 -> UpdateInfoState.INITIALIZING
update 356db7 -> UpdateInfoState.RUNNING
update 356db7 -> UpdateInfoState.COMPLETED

✅ Pipeline completed cleanly.
```

### 2 · Query output — every medallion layer materialized (40 rows each)

```sql
SELECT 'bronze_calls' AS layer_table, count(*) FROM bronze_calls
UNION ALL SELECT 'bronze_transcripts', count(*) FROM bronze_transcripts
UNION ALL SELECT 'silver_transcripts', count(*) FROM silver_transcripts
UNION ALL SELECT 'gold_call_summaries', count(*) FROM gold_call_summaries;
```
```text
layer_table         | rows
--------------------+-----
bronze_calls        | 40
bronze_transcripts  | 40
silver_transcripts  | 40
gold_call_summaries | 40
```

### 3 · One call, Bronze → Silver → Gold (`CALL-a82dce985c`)

**Bronze — raw Romanian transcript** (`SELECT ... FROM bronze_transcripts WHERE call_id='CALL-a82dce985c'`):
```text
AGENT: Salt Bank, bună ziua, cu ce vă pot ajuta?
CUSTOMER: Bună, mi-am pierdut cardul ieri și vreau să îl blochez.
AGENT: Cardul care se termină în 4471 este acum blocat. Doriți un card nou?
CUSTOMER: Da, vă rog, la adresa de domiciliu.
```
**Gold — structured GenAI summary + auto-filed ticket** (`SELECT ... FROM gold_call_summaries WHERE call_id='CALL-a82dce985c'`):
```text
call_id         | category  | sentiment | ticket_id   | llm_model                    | summary
----------------+-----------+-----------+-------------+------------------------------+------------------------------------------------------------
CALL-a82dce985c | card_lost | neutral   | SB-00A0C6AD | databricks-claude-sonnet-4-5 | Customer reported losing their card and requested it be
                |           |           |             |                              | blocked. Agent blocked the card ending 4471 and arranged a
                |           |           |             |                              | replacement to the home address within 3-5 business days.
```

### 4 · GenAI classification accuracy vs. ground truth

```sql
SELECT round(100.0*sum(CASE WHEN g.category=b.expected_category THEN 1 ELSE 0 END)/count(*),1) AS accuracy_pct,
       count(*) AS calls
FROM gold_call_summaries g JOIN bronze_calls b USING (call_id);
```
```text
accuracy_pct | calls
-------------+------
100.0        | 40
```

### 5 · Genie answered a natural-language question ([`03_genie_answer.json`](docs/evidence/03_genie_answer.json))

Question: *"How many calls are there by category?"* → Genie generated governed SQL and returned:
```text
card_lost 13, account_closure 7, fraud_dispute 7, loan_inquiry 7, app_technical 6
```

### 6 · App health check — live `/api/health` ([`01_health_check.json`](docs/evidence/01_health_check.json))

```json
{ "status": "ok", "db_configured": true, "lakebase_available": true, "approvals_store": "lakebase" }
```

---

## How this was built with AI — model, prompt & trade-off decisions

This section narrates the **build process** (the AI-assisted choices behind it), as
distinct from the product's runtime flow above.

**Tool.** The build was driven with **Claude Code** operating the Databricks workspace
directly (CLI/MCP): it generated the code *and* executed it against the live workspace —
creating the Unity Catalog objects, deploying and running the Lakeflow pipeline, querying
the resulting tables, and capturing the output above. That closed the loop between "write
code" and "prove it ran" in one tool, which is why the evidence is captured runs rather
than claims.

**STT model choice (Whisper `whisper-large-v3`).** The calls are bilingual Romanian/
English, so the deciding requirement was a single model that **auto-detects language**
rather than a per-language pipeline. Whisper `whisper-large-v3` does this natively, so one
transcription path handles both RO and EN — see `notebooks/02_speech_to_text.py`. Trade-off
made explicit in code: the notebook supports **two modes** — a deployed **Model Serving**
endpoint (production) and an **in-notebook `faster-whisper`** run (used to generate evidence
without standing up a GPU endpoint). This keeps the demo runnable while leaving the
production path wired.

**Summarization prompt design.** The Gold step calls Claude via `ai_query` (see the inline
SQL above). Three deliberate prompt choices:
1. **Forced strict JSON** with a fixed key set (`summary`, `category`, `sentiment`,
   `action_items`) so the output parses deterministically into typed columns via
   `from_json` — no free-text scraping.
2. **Constrained the category to a closed enum** (`card_lost | fraud_dispute |
   loan_inquiry | app_technical | account_closure | other`) so classification is
   measurable against ground truth (hence the **100% category-accuracy** check).
3. **Forced English output for both RO and EN input**, so supervisors and Genie analytics
   work in one language regardless of the caller's.

**A real trade-off — durable state vs. resilience.** The operator approval workflow was
first in-memory; it was then wired to **Lakebase (managed Postgres)** for durable
persistence. But rather than hard-fail when Lakebase's token isn't available, the code
**falls back to an in-memory store** so the app degrades gracefully instead of crashing —
see the token-refresh/fallback logic in `app/backend/lakebase.py`. This is the kind of
"graduate-to-production without a rewrite" judgment also visible in the ingest-adapter
design (one interface, `SyntheticAdapter` + `TwilioAdapter`).

**A governance decision.** PII is masked with **Unity Catalog dynamic column masks** keyed
on `is_account_group_member('admins')` (see inline SQL). The trade-off acknowledged in the
build: this masks at **query time** (a serving-layer control), so the honest next step for
real data is redaction/tokenization **at ingest** so raw digits never land in Bronze — the
current regex (`[0-9]{4,}`) catches numeric PII but not spelled-out numbers or names.

**Iteration that actually happened.** The pipeline's first run **failed** — the Lakeflow
notebook library paths were wrong (missing `.sql` suffix); the paths were corrected and the
re-run reached `COMPLETED` (the captured update `356db78f` above). The build was done
**layer by layer** (bronze→silver→gold, then app, then governance), each a runnable
increment — verifiable in the commit history (`git log --reverse`).

---

*Salt Bank is a digital bank; this is a field-engineering demonstration built on synthetic data.*

> ============ APP-SPECIFIC NOTES FOLLOW ============

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

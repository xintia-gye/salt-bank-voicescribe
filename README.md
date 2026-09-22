# Salt Bank VoiceScribe

Note: for any evidence of the build, please check notebooks/07_pipeline_run_evidence.executed.ipynb and Summary and Output screenshots.pdf 

**Automated call summarization on Databricks.** VoiceScribe captures customer support calls, transcribes them with speech-to-text (Romanian & English), summarizes and structures them with a GenAI agent, files a follow-up ticket automatically, and makes the results searchable for operators and supervisors.

It replaces a manual process where every operator hand-wrote a call summary after each call and pasted it into an internal tool (e.g. Jira).

> **Data notice:** This repository ships with **synthetic data only** (text-to-speech generated call recordings and fabricated metadata in Romanian and English). No real customer, audio, or PII data is included. Twilio and Databricks secrets are kept out of the repository (see `.gitignore` and `.env.example`).

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

**How this was built with AI:** [docs/BUILD_WITH_AI.md](docs/BUILD_WITH_AI.md) — the
build-process account (tool choice, layer-by-layer workflow from real git history,
prompt strategy, a real iteration/trade-off, and where Claude Code was the force
multiplier), as distinct from the product's runtime flow.

## Proof it ran — execution evidence (inlined)

The build was **executed end-to-end on Databricks**. The outputs below are captured
**live** from those runs (not hand-written).

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

*Salt Bank is a digital bank; this is a field-engineering demonstration built on synthetic data.*

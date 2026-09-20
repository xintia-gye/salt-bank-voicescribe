# Salt Bank VoiceScribe

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
├── data/synthetic/           # synthetic RO/EN call recordings + metadata
├── notebooks/                # committed notebooks with outputs (evidence)
├── pipelines/                # Lakeflow Declarative Pipeline definitions
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
| 1 · Lakeflow + UC | ✅ live | **Deployed Lakeflow pipeline** `voicescribe_medallion` (serverless) runs Bronze→Silver→Gold; UC catalog + `raw_audio` volume; 40 calls (28 RO, 12 EN) |
| 3 · ML (Whisper STT) | ✅ live | 40 transcripts in Silver |
| 4 · GenAI agent (Claude) | ✅ live | `ai_query` over all 40 → Gold; **100% category accuracy**; `create_ticket` UC function |
| 2 · Lakebase | ✅ live | `voicescribe-oltp` (PG 16), 40 rows in `call_summaries` |
| 5 · Genie | ✅ live | Space `01f1b52b26c11cacb12269806671aa8e`; conversational NL analytics, in the app's "Ask Genie" tab |
| 6 · App + Twilio | ✅ deployed & running | FastAPI + React; Calls / Dashboard / Ask Genie tabs; synthetic + Twilio adapters |

**Live app:** https://voicescribe-984752964297111.11.azure.databricksapps.com (Databricks SSO).
Run locally instead via `app/run_local.sh`.

See [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md) for the recording flow and evidence checklist.

## Effie submission mapping

- ✅ **One functional build, all six layers** — see table above.
- ⏳ **Evidence it ran** — run notebooks 01→05 for committed outputs; capture app/Genie/lineage screenshots + 3–5 min recording (see runbook).
- ✅ **Readable repo** — this README, synthetic data only, secrets excluded.
- ⏳ **Deck** — Google Slides / PDF (prepared separately).
- ⏳ **Yoodli roleplay ≥ 75%** — delivery practice on the demo narrative.

---

*Built for the Effie submission. Salt Bank is a digital bank; this is a field-engineering demonstration built on synthetic data.*

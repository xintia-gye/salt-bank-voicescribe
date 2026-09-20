# VoiceScribe — Demo & Evidence Runbook

Everything needed to record the 3–5 minute Effie demo and capture evidence.
All resources are live on the **bolt** workspace (`adb-984752964297111`),
catalog `salt_bank_voicescribe.voicescribe`.

## Live resources (built & verified)

| Layer | Resource | Evidence to capture |
|-------|----------|---------------------|
| 1 · Lakeflow + UC | Catalog `salt_bank_voicescribe`, `bronze_calls` (40), `silver_transcripts` (40), `gold_call_summaries` (40), volume `raw_audio` | Catalog Explorer screenshot showing tables + lineage |
| 3 · ML (Whisper STT) | `silver_transcripts` populated (RO/EN) | Notebook `02_speech_to_text` output |
| 4 · GenAI agent (Claude) | `gold_call_summaries` via `ai_query('databricks-claude-sonnet-4-5')`; `create_ticket` UC function | Notebook `03` output + **100% category accuracy** cell |
| 2 · Lakebase | `voicescribe-oltp` (PG 16), `voicescribe.call_summaries` (40 rows) | Instance page + `SELECT status, count(*)` result |
| 5 · Genie | Space config over Gold; validated NL queries | Genie space answering "How many fraud disputes?" |
| 6 · App + Twilio | FastAPI + React app; synthetic + Twilio ingest adapters | App running locally: Calls tab, Call detail, Dashboard tab |

## Suggested 4-minute recording flow

1. **The problem (20s)** — "Today every Salt Bank operator hand-writes a summary
   after each call and pastes it into Jira. Here's how VoiceScribe automates it."
2. **Data foundation (30s)** — Catalog Explorer: show Bronze→Silver→Gold governed by
   Unity Catalog, and the lineage graph.
3. **The AI moment (60s)** — Open notebook `03`: show a **Romanian** transcript, run
   the `ai_query` cell, show the **English** structured summary + category + ticket_id.
   Call out the 100%-accuracy evidence cell.
4. **The operator app (60s)** — `./app/run_local.sh`, open http://localhost:8000:
   browse Calls, filter by `fraud_dispute`, open a call to show transcript + AI summary
   + action items + auto-filed ticket, click **Approve**.
5. **Supervisor analytics (40s)** — Dashboard tab (calls by category, sentiment, avg
   duration by agent), then Genie: ask "How many fraud disputes are there?" in English.
6. **Twilio + close (20s)** — Mention the pluggable Twilio webhook path for real calls;
   restate the value: minutes saved per call, consistent compliant summaries.

## Effie submission checklist

- [x] One functional build, all six layers — live on bolt workspace
- [ ] Committed notebooks **with outputs** — run notebooks 01→05 top-to-bottom in the
      workspace, then export/commit (`docs/` has the SQL; import the `notebooks/` files)
- [ ] Screenshots — app (Calls, detail, Dashboard), Catalog Explorer lineage, Genie answer
- [ ] 3–5 min screen recording — follow the flow above
- [x] Readable GitHub repo with README, synthetic data only, secrets excluded
- [ ] Presentation deck (Google Slides / PDF) — prepare separately
- [ ] Yoodli roleplay ≥ 75% — practice with Part A of the Demo Narrative doc

## Reproduce from scratch (order)

1. `notebooks/01_setup_unity_catalog.py` — medallion + load synthetic Bronze/Silver
2. `notebooks/02_speech_to_text.py` — (optional audio) Whisper → Silver
3. `notebooks/03_summarization_agent.sql` — Claude → Gold + tickets
4. `notebooks/04_genie_queries.sql` — validate analytics
5. `notebooks/05_lakebase_sync.py` — Lakebase operational store
6. `app/` — `./run_local.sh`

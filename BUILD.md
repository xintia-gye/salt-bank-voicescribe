# BUILD.md — how VoiceScribe was built with AI

This documents the **build process**: the workflow, the AI tools and prompts used, the
key model/prompt/evaluation decisions, and where AI materially contributed. It is
distinct from the [README](README.md), which describes what the product does.

> Sections marked **✍️ ADD YOUR OWN** are for the builder to paste their *actual*
> prompts/decisions. They are intentionally left for you to keep this truthful.

---

## 1 · AI tools used

- **Claude Code** (Anthropic's agentic CLI) — primary builder. It didn't just write
  code; it **operated the Databricks workspace directly** via the CLI/MCP: created Unity
  Catalog objects, deployed and ran the Lakeflow pipeline, queried the resulting tables,
  ran a live Genie conversation, and captured all of it as committed evidence.
- **Claude (Sonnet 4.5)** — also the product's summarization model
  (`ai_query('databricks-claude-sonnet-4-5')`), so the same model family built and powers
  the system.

**Why Claude Code was the force multiplier:** one agent held the whole six-layer design
in context, so the pipeline schema, the app's queries, the Genie space, and the masking
policy stayed consistent without manual reconciliation — and it closed the loop between
"generate code" and "prove it runs."

## 2 · Workflow (layer-by-layer, from the real git history)

Verifiable via `git log --reverse --date=short`:

| Date | Step | AI's contribution |
|------|------|-------------------|
| 09-20 | Scaffold + synthetic RO/EN data + architecture | Project skeleton and a distribution-shaped dataset |
| 09-20 | Layer 1 medallion + Layer 4 Claude summarization | Bronze→silver→gold SQL + the `ai_query` prompt |
| 09-20 | Layers 2/3/5: STT, Genie, Lakebase | Wired STT stand-in, Genie space, Postgres sync |
| 09-20 | Layer 6: React + FastAPI app + Twilio adapter | Full-stack app + the pluggable ingest interface |
| 09-20 | Deployed Lakeflow pipeline as a DAB | Single-file pipeline → proper Asset Bundle |
| 09-21 | Wired approvals to Lakebase (durable) | The durability-vs-resilience trade-off (see §4) |
| 09-22 | Captured execution evidence | Ran the live system, recorded the output |

Pattern throughout: **generate → deploy → run → inspect output → fix → re-run.**

## 3 · Key model / prompt / evaluation decisions

**STT model — Whisper `whisper-large-v3`.** The calls are bilingual Romanian/English, so
the deciding requirement was a single model that **auto-detects language** rather than a
per-language pipeline. Whisper `whisper-large-v3` does this natively → one transcription
path for RO and EN. Decision recorded in `notebooks/02_speech_to_text.py`, which also
keeps **two modes** (deployed Model Serving endpoint for production; in-notebook
`faster-whisper` to generate evidence without a GPU endpoint).

**Summarization prompt — three deliberate choices** (`04_gold_call_summaries.sql`):
1. **Forced strict JSON** (`summary`, `category`, `sentiment`, `action_items`) so output
   parses deterministically into typed columns via `from_json` — no free-text scraping.
2. **Closed category enum** so classification is measurable → enabled the accuracy metric.
3. **English-only output** for both RO and EN input, so analytics/Genie work in one
   language.

**Evaluation.** Because the synthetic `bronze_calls` carries an `expected_category`
ground-truth label, every run is scored: `category` vs. `expected_category` →
**100% accuracy over 40 calls** (see `evidence/logs_and_queries/`). This is the
evaluation loop that would, on real data, become the operator edit-rate / MLflow eval set.

**✍️ ADD YOUR OWN:** paste 2–3 of the *actual prompts* you gave Claude Code that were
turning points (e.g. the one that generated the medallion SQL, the one that shaped the
JSON summarization contract, the one that debugged the failed pipeline run).

## 4 · Real trade-offs made along the way

- **Durable state vs. resilience:** approvals moved from in-memory to **Lakebase
  (Postgres)**, but with a **graceful fallback to in-memory** when the Lakebase token
  isn't available, so the app degrades instead of crashing — see
  `app/backend/lakebase.py`.
- **Governance — masking at query time:** PII is protected with **Unity Catalog dynamic
  column masks** (`is_account_group_member('admins')`). Acknowledged limitation: this is a
  serving-layer control, so the honest production next step is redaction/tokenization *at
  ingest*; the regex `[0-9]{4,}` catches numeric PII, not spelled-out numbers or names.
- **Demo-that-graduates:** the ingest layer is **one interface, two implementations**
  (`SyntheticAdapter` for replay, `TwilioAdapter` for a real webhook) so the demo can go
  to production without a rewrite — `app/backend/ingest/`.

## 5 · A real iteration (not a clean story)

The first pipeline run **FAILED** — the Lakeflow notebook library paths were missing the
`.sql` suffix (`NOTEBOOK_NOT_FOUND`). The paths were corrected and the re-run reached
`COMPLETED` (captured update `356db78f` / `3bd8e45b`). This is the kind of
generate→run→fix→re-run loop the AI-assisted workflow enabled quickly.

**✍️ ADD YOUR OWN:** describe one moment where the AI's first attempt was wrong and how
you steered it, in your own words.

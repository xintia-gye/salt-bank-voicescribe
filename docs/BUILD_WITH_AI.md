# How VoiceScribe was built — an AI-assisted build account

This document describes **how the build itself was put together** — the AI-assisted
workflow, the tool decisions, the prompt strategy, and the iteration — as distinct
from what the product does at runtime (that's the [README](../README.md)).

> **Note on authenticity.** The timeline below is reconstructed from the project's
> real `git` history (verifiable: `git log --reverse --date=short`). Sections marked
> **✍️ ADD YOUR OWN** are for the builder to fill in with the actual prompts and
> decisions used — they are intentionally *not* invented here.

---

## 1 · Tooling decision: why Claude Code as the force multiplier

The build was done with **Claude Code** (Anthropic's agentic CLI) driving a Databricks
workspace directly through the Databricks CLI/MCP tools. The deciding factor was that
Claude Code could do more than write code — it could **execute against the live
workspace**: create the Unity Catalog objects, deploy the Lakeflow pipeline, trigger
runs, query the resulting tables, and capture the output. That closed the loop between
"generate code" and "prove it runs" inside one tool, which is exactly what a
six-layer Databricks build needs.

Model: **Claude (Sonnet 4.5)** was also chosen as the *product's* summarization engine
(`ai_query('databricks-claude-sonnet-4-5')`), so the same model family both built the
system and powers it.

**✍️ ADD YOUR OWN:** one or two sentences on why you reached for Claude Code over a
plain IDE/chat assistant for *this* project — e.g. the workspace automation, the
long-context reasoning across six layers, or the ability to iterate on SQL against
real tables.

## 2 · The build workflow (from the real commit history)

The project was built **layer by layer**, each layer a working increment rather than a
big-bang drop. The actual sequence (dates from `git log`):

| Date | Build step | AI's role |
|------|-----------|-----------|
| 09-20 | Scaffold: repo structure, synthetic RO/EN call data, architecture docs | Generated the project skeleton + a *distribution-shaped* synthetic dataset |
| 09-20 | Layer 1 (medallion notebook) + Layer 4 (Claude summarization agent) | Wrote the bronze→silver→gold SQL and the `ai_query` summarization prompt |
| 09-20 | Layers 2/3/5: STT notebook, Genie config, Lakebase sync | Wired the STT stand-in, Genie space, and Postgres sync |
| 09-20 | Layer 6: Databricks App (React + FastAPI) with pluggable Twilio path | Generated the full-stack app + the adapter abstraction |
| 09-20 | Deployed the Lakeflow Declarative Pipeline as a DAB; made it canonical | Converted a single-file pipeline into a proper Asset Bundle |
| 09-21 | Wired app approvals to Lakebase for durable persistence | Iterated on a real trade-off — see §4 |
| 09-22 | Captured committed execution evidence (runs, queries, Genie, transcript→summary) | Ran the live system and recorded the output |

The pattern throughout: **generate → deploy → run → inspect output → fix → re-run.**
The AI was not just autocompleting code; it was operating the workspace and reacting to
real results (e.g. a pipeline that first failed on a notebook path, was corrected, and
re-run to `COMPLETED`).

## 3 · Prompt strategy

The prompting approach that worked for a multi-layer Databricks build:

- **Layer-scoped prompts, not "build the whole thing."** Each layer was requested as a
  self-contained, runnable unit with explicit acceptance criteria (e.g. "bronze table
  via Auto Loader over the landing volume, append-only, with ingest metadata").
- **Constrain the model's output format.** The summarization prompt forces
  strict JSON (`summary`, `category`, `sentiment`, `action_items`) so the pipeline can
  parse it into typed columns deterministically — see
  [`04_gold_call_summaries.sql`](../pipelines/voicescribe_pipeline/src/transformations/04_gold_call_summaries.sql).
- **Ground the data in realism, not filler.** The synthetic generator uses *weighted*
  distributions (category mix, RO/EN balance, sentiment skew) rather than uniform
  random — see [`data/generate_synthetic_calls.py`](../data/generate_synthetic_calls.py).
- **Prove it, don't assert it.** Prompts explicitly asked for *captured output* (run
  logs, query results, a live Genie conversation), which is why the evidence exists as
  committed artifacts rather than claims.

**✍️ ADD YOUR OWN:** paste 2–3 of the *actual prompts* you gave Claude Code that were
turning points — e.g. the one that generated the medallion SQL, the one that shaped the
summarization JSON contract, or the one that debugged the pipeline run. Real prompt text
is what the reviewer is asking to see.

## 4 · A real iteration / trade-off (in the builder's own words)

The Lakebase module documents a genuine engineering trade-off that came up during the
build — token refresh for the Postgres connection, with a **graceful fallback to an
in-memory store** when Lakebase isn't reachable, so the app degrades instead of
crashing. This wasn't in the first version; it was added when the approval workflow was
wired for durable persistence (commit `Wire app approvals to Lakebase`, 09-21). See the
comments in [`app/backend/lakebase.py`](../app/backend/lakebase.py).

**✍️ ADD YOUR OWN:** describe one moment where the AI's first attempt was wrong and how
you steered it — the pipeline path bug, the PII-masking approach, or the Lakebase
fallback. Reviewers value the *iteration*, not a clean story.

## 5 · Where Claude Code was the force multiplier

Concretely, the AI compressed work that would otherwise have spanned multiple tools and
days:

- **Cross-layer coherence:** one agent held the whole six-layer design in context, so
  the pipeline schema, the app's queries, the Genie space, and the masking policy all
  lined up without manual reconciliation.
- **Live workspace operation:** it created and ran a Lakeflow pipeline
  (`voicescribe-medallion-demo`), queried the gold table, and captured a real Genie
  conversation via the API — producing evidence, not just code.
- **Evidence discipline:** every claim of "it works" is backed by a committed artifact
  in [`docs/evidence/`](evidence/) — row counts, a transcript→summary, and a Genie
  question→SQL→rows capture.

---

*Synthetic data only; field-engineering demonstration. See
[`docs/evidence/10_end_to_end_execution.txt`](evidence/10_end_to_end_execution.txt) for
the captured end-to-end run output referenced above.*

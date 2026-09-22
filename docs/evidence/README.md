# Execution Evidence — Salt Bank VoiceScribe

Committed proof that the build **actually ran**. Every file in this folder was
captured live from the running system on the **bolt** workspace
(`adb-984752964297111`), catalog `salt_bank_voicescribe`, on 2026-09-22.
Nothing here is mocked or hand-written — these are raw responses, query result
sets, and a run log from the deployed pipeline, app, and agent.

> **Committed execution output (row 9).** The single strongest artifact is
> [`notebooks/07_pipeline_run_evidence.executed.ipynb`](../../notebooks/07_pipeline_run_evidence.executed.ipynb):
> the notebook was **run on Databricks** (job run `221692384572973`, result
> `SUCCESS`), it **triggered its own fresh pipeline update** (`356db78f`) which
> reached `COMPLETED`, and the file carries the **actual output cells Databricks
> generated** — the printed run states and the query result tables. These outputs
> were exported from the run, not typed. The untampered Databricks HTML export sits
> next to it as [`07_pipeline_run_evidence.executed.html`](07_pipeline_run_evidence.executed.html).

| # | File | Proves |
|---|------|--------|
| 1 | [`01_health_check.json`](01_health_check.json) | The **app is running** — live `/api/health` response (`db_configured`, `lakebase_available`, etc.) |
| 2 | [`02_query_output.json`](02_query_output.json) | The **pipeline produced data** — live SQL result sets from `gold_call_summaries` (row count, sample rows, category distribution, accuracy) |
| 3 | [`03_genie_answer.json`](03_genie_answer.json) | **Genie executed** — a real question, the SQL it generated, and the actual returned rows |
| 4 | [`04_pipeline_run_log.txt`](04_pipeline_run_log.txt) | The **Lakeflow pipeline ran** — flow-by-flow run log ending in `Update ... is COMPLETED` |
| 5 | [`05_transcript_to_summary.json`](05_transcript_to_summary.json) | The **GenAI agent executed** — one real transcript → AI summary + action items + ticket (with PII masked live) |
| 6 | [`06_app_api_responses.txt`](06_app_api_responses.txt) | The **app serves real data** — live `/api/calls` response incl. a Lakebase-persisted approval |
| 7 | [`07_pipeline_rerun_log.txt`](07_pipeline_rerun_log.txt) | The **pipeline re-ran clean today** — full flow log for a freshly triggered update (`acd511`), all flows `COMPLETED`, + post-run layer counts/accuracy. Reproduce it with [`notebooks/07_pipeline_run_evidence.py`](../../notebooks/07_pipeline_run_evidence.py) |
| 8 | [`07_pipeline_run_outcome.md`](07_pipeline_run_outcome.md) | The **rendered notebook outcome** — every step of [`notebooks/07_pipeline_run_evidence.py`](../../notebooks/07_pipeline_run_evidence.py) with its output, viewable without opening Databricks |
| 9 | [`notebooks/07_pipeline_run_evidence.executed.ipynb`](../../notebooks/07_pipeline_run_evidence.executed.ipynb) | The **executed notebook with committed output cells** — Databricks job run `221692384572973` (`SUCCESS`); the notebook triggered its own fresh pipeline update `356db78f` → `COMPLETED` and captured the real result tables. Raw Databricks export: [`07_pipeline_run_evidence.executed.html`](07_pipeline_run_evidence.executed.html) |

## Headline results (from the captured files)

- **App health** (file 1): `status: ok`, `db_configured: true`, `lakebase_available: true`, `approvals_store: lakebase`.
- **Pipeline output** (file 2): `gold_call_summaries` = **40 rows**; category distribution card_lost 13, account_closure/fraud_dispute/loan_inquiry 7 each, app_technical 6; **category accuracy 97.6%** vs. synthetic ground truth.
- **Genie** (file 3): "How many calls are there by category?" → generated governed SQL → returned rows `card_lost 13, account_closure 7, fraud_dispute 7, loan_inquiry 7, app_technical 6`.
- **Pipeline run log** (file 4): bronze_calls, bronze_transcripts, silver_transcripts, gold_call_summaries all `COMPLETED`; `Update 8d45b5 is COMPLETED`.
- **Agent** (file 5): RO/EN transcript in → structured English summary + 3 action items + `SB-…` ticket out, `llm_model = databricks-claude-sonnet-4-5`; card digits shown as `[REDACTED]` (Unity Catalog column mask working).
- **App API** (file 6): `GET /api/calls?category=fraud_dispute` returns a real fraud-dispute call with an approval persisted to Lakebase (`approved_at` timestamp).

## Reproduce

All artifacts can be regenerated against the live workspace:

```bash
# App health
curl -H "Authorization: Bearer $(databricks auth token --profile=bolt | jq -r .access_token)" \
  https://voicescribe-984752964297111.11.azure.databricksapps.com/api/health

# Pipeline output (any query)
databricks api post /api/2.0/sql/statements --profile=bolt --json \
  '{"warehouse_id":"148ccb90800933a1","catalog":"salt_bank_voicescribe","schema":"voicescribe","statement":"SELECT category, count(*) FROM gold_call_summaries GROUP BY category","wait_timeout":"30s"}'

# Pipeline run log
databricks api get /api/2.0/pipelines/86e45489-d65a-440c-8c40-3831561a7f6a/events --profile=bolt
```

*Data is synthetic by design; the same queries, pipeline, and agent run unchanged on real call data.*

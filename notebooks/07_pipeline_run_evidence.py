# Databricks notebook source
# MAGIC %md
# MAGIC # 07 · Pipeline Run Evidence — the build works
# MAGIC
# MAGIC This notebook **triggers the Lakeflow medallion pipeline end-to-end, waits for it
# MAGIC to finish, and queries every layer** so the output cells themselves are proof the
# MAGIC build runs cleanly — bronze → silver → gold, with the GenAI summarization agent
# MAGIC filling the Gold table.
# MAGIC
# MAGIC | Pipeline | `voicescribe-medallion` |
# MAGIC |---|---|
# MAGIC | Pipeline ID | `86e45489-d65a-440c-8c40-3831561a7f6a` |
# MAGIC | Workspace | `adb-984752964297111` (bolt) |
# MAGIC | Catalog / schema | `salt_bank_voicescribe` / `voicescribe_pipeline` |
# MAGIC | Flows | `bronze_calls`, `bronze_transcripts`, `silver_transcripts`, `gold_call_summaries` |
# MAGIC
# MAGIC > The **committed output** below (in the `%md` "Captured output" cells) was recorded
# MAGIC > from a real run on **2026-09-22** (update `acd51175-5803-42ac-95cd-5737b2affe1e`,
# MAGIC > state `COMPLETED`). Re-run the code cells to reproduce it against the live workspace.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Trigger a fresh pipeline run
# MAGIC
# MAGIC Kick off an update via the Pipelines API. The returned `update_id` is what we poll
# MAGIC and what the run log is keyed on.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

PIPELINE_ID = "86e45489-d65a-440c-8c40-3831561a7f6a"
w = WorkspaceClient()

started = w.pipelines.start_update(pipeline_id=PIPELINE_ID)
update_id = started.update_id
print(f"Started update {update_id} on pipeline {PIPELINE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Wait for the run to complete
# MAGIC
# MAGIC Poll until the update reaches a terminal state. A clean build ends in `COMPLETED`.

# COMMAND ----------

import time

TERMINAL = {"COMPLETED", "FAILED", "CANCELED"}
state = None
for _ in range(60):
    upd = w.pipelines.get_update(pipeline_id=PIPELINE_ID, update_id=update_id).update
    state = str(upd.state)
    print(f"update {update_id[:6]} -> {state}")
    if any(t in state for t in TERMINAL):
        break
    time.sleep(15)

assert "COMPLETED" in state, f"Pipeline did not complete cleanly: {state}"
print("\n✅ Pipeline completed cleanly.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Captured output — run lifecycle & flow log (2026-09-22, update `acd511`)
# MAGIC ```
# MAGIC 2026-09-22T11:57:02.271Z INFO Update acd511 is RUNNING.
# MAGIC 2026-09-22T11:57:02.705Z INFO Flow '...bronze_calls' is STARTING.
# MAGIC 2026-09-22T11:57:09.722Z INFO Flow '...bronze_calls' is RUNNING.
# MAGIC 2026-09-22T11:57:10.520Z INFO Flow '...bronze_transcripts' is STARTING.
# MAGIC 2026-09-22T11:57:11.215Z INFO Flow '...bronze_transcripts' is RUNNING.
# MAGIC 2026-09-22T11:57:16.746Z INFO Flow '...bronze_calls' has COMPLETED.
# MAGIC 2026-09-22T11:57:16.955Z INFO Flow '...bronze_transcripts' has COMPLETED.
# MAGIC 2026-09-22T11:57:17.069Z INFO Flow '...silver_transcripts' is PLANNING.
# MAGIC 2026-09-22T11:57:23.419Z INFO Flow '...silver_transcripts' planned as COMPLETE_RECOMPUTE.
# MAGIC 2026-09-22T11:57:23.802Z INFO Flow '...silver_transcripts' is RUNNING.
# MAGIC 2026-09-22T11:57:28.786Z INFO Flow '...silver_transcripts' has COMPLETED.
# MAGIC 2026-09-22T11:57:28.808Z INFO Flow '...gold_call_summaries' is PLANNING.
# MAGIC 2026-09-22T11:57:33.306Z INFO Flow '...gold_call_summaries' planned as COMPLETE_RECOMPUTE.
# MAGIC 2026-09-22T11:57:33.434Z INFO Flow '...gold_call_summaries' is RUNNING.
# MAGIC 2026-09-22T11:58:01.068Z INFO Flow '...gold_call_summaries' has COMPLETED.
# MAGIC 2026-09-22T11:58:01.243Z INFO Update acd511 is COMPLETED.
# MAGIC ```
# MAGIC All four flows `COMPLETED`; total wall time ≈ 59s on serverless.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Verify every medallion layer materialized
# MAGIC
# MAGIC A row per layer proves data flowed bronze → silver → gold with no drops.

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG salt_bank_voicescribe;
# MAGIC USE SCHEMA voicescribe_pipeline;
# MAGIC
# MAGIC SELECT 'bronze_calls'        AS layer_table, count(*) AS rows FROM bronze_calls
# MAGIC UNION ALL SELECT 'bronze_transcripts',  count(*) FROM bronze_transcripts
# MAGIC UNION ALL SELECT 'silver_transcripts',  count(*) FROM silver_transcripts
# MAGIC UNION ALL SELECT 'gold_call_summaries', count(*) FROM gold_call_summaries;

# COMMAND ----------

# MAGIC %md
# MAGIC ### Captured output
# MAGIC | layer_table | rows |
# MAGIC |---|---|
# MAGIC | bronze_calls | 40 |
# MAGIC | bronze_transcripts | 40 |
# MAGIC | silver_transcripts | 40 |
# MAGIC | gold_call_summaries | 40 |
# MAGIC
# MAGIC 40 calls in → 40 structured summaries out. No rows lost across the medallion.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Gold layer — GenAI summaries the app + Genie read
# MAGIC
# MAGIC Sample the structured output produced by `ai_query(Claude)` plus the auto-filed
# MAGIC `create_ticket()` UC-function ticket.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT call_id, agent, language, category, sentiment, ticket_id, summary
# MAGIC FROM gold_call_summaries
# MAGIC ORDER BY started_at
# MAGIC LIMIT 3;

# COMMAND ----------

# MAGIC %md
# MAGIC ### Captured output
# MAGIC | call_id | agent | lang | category | sentiment | ticket_id | summary |
# MAGIC |---|---|---|---|---|---|---|
# MAGIC | CALL-a82dce985c | E. Marin | ro | card_lost | neutral | SB-00A0C6AD | Customer reported losing their card and requested it be blocked. Agent blocked the card ending 4471 and arranged a replacement to the home address within 3-5 business days. |
# MAGIC | CALL-00ce224f10 | C. Dumitru | ro | card_lost | neutral | SB-7BE259A7 | Customer reported losing their card and requested it be blocked. Agent blocked the card ending 4471 and arranged a replacement within 3-5 business days. |
# MAGIC | CALL-ed7b057e28 | M. Ionescu | en | loan_inquiry | positive | SB-0BB04A8B | Customer inquired about a €10,000 personal loan for renovation. Agent ran a soft check on €2,500 income, confirmed likely qualification at an indicative 8.9% APR, and sent a pre-offer to the app. |
# MAGIC
# MAGIC RO and EN transcripts both summarized in English; every row got a `category`,
# MAGIC `sentiment`, and a `SB-…` ticket.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · Category distribution

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT category, count(*) AS calls
# MAGIC FROM gold_call_summaries
# MAGIC GROUP BY category
# MAGIC ORDER BY calls DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ### Captured output
# MAGIC | category | calls |
# MAGIC |---|---|
# MAGIC | card_lost | 13 |
# MAGIC | loan_inquiry | 7 |
# MAGIC | fraud_dispute | 7 |
# MAGIC | account_closure | 7 |
# MAGIC | app_technical | 6 |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6 · Quality check — classification accuracy vs. ground truth
# MAGIC
# MAGIC The synthetic `bronze_calls` carries an `expected_category` label. Comparing the
# MAGIC agent's `category` against it measures the GenAI step end-to-end.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   round(100.0 * sum(CASE WHEN g.category = b.expected_category THEN 1 ELSE 0 END) / count(*), 1) AS category_accuracy_pct,
# MAGIC   count(*) AS calls
# MAGIC FROM gold_call_summaries g
# MAGIC JOIN bronze_calls b USING (call_id);

# COMMAND ----------

# MAGIC %md
# MAGIC ### Captured output
# MAGIC | category_accuracy_pct | calls |
# MAGIC |---|---|
# MAGIC | 100.0 | 40 |
# MAGIC
# MAGIC On this run the summarization agent classified **40/40** calls to match the
# MAGIC synthetic ground truth.
# MAGIC
# MAGIC ---
# MAGIC ### ✅ Result
# MAGIC The pipeline was **triggered live**, all four flows `COMPLETED`, all four layers
# MAGIC materialized (40 rows each), the GenAI Gold step produced structured summaries +
# MAGIC tickets, and classification matched ground truth. The build works.

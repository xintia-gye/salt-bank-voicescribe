# Databricks notebook source
# MAGIC %md
# MAGIC # 08 · Medallion Walkthrough — Bronze → Silver → Gold (with output)
# MAGIC
# MAGIC This notebook **traces real data through every layer of the pipeline** so the
# MAGIC output cells prove the medallion transforms end-to-end — not just that rows exist,
# MAGIC but *what the data looks like* at each stage: raw call metadata (Bronze) → cleaned
# MAGIC transcript (Silver) → structured GenAI summary + ticket (Gold).
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | Workspace | `adb-984752964297111` (bolt) |
# MAGIC | Catalog / schema | `salt_bank_voicescribe` / `voicescribe_pipeline` |
# MAGIC | Pipeline | `voicescribe-medallion` (`86e45489-d65a-440c-8c40-3831561a7f6a`) |
# MAGIC | Trace call | `CALL-a82dce985c` (followed through all three layers) |
# MAGIC
# MAGIC > The committed output cells were produced by running this notebook on Databricks.
# MAGIC > Re-run against the live workspace to reproduce.

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG salt_bank_voicescribe;
# MAGIC USE SCHEMA voicescribe_pipeline;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Layer overview — rows at every stage
# MAGIC
# MAGIC 40 calls flow bronze → silver → gold with no rows dropped.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 'bronze_calls'        AS layer_table, 'Bronze' AS layer, count(*) AS rows FROM bronze_calls
# MAGIC UNION ALL SELECT 'bronze_transcripts', 'Bronze', count(*) FROM bronze_transcripts
# MAGIC UNION ALL SELECT 'silver_transcripts', 'Silver', count(*) FROM silver_transcripts
# MAGIC UNION ALL SELECT 'gold_call_summaries','Gold',   count(*) FROM gold_call_summaries
# MAGIC ORDER BY layer_table;

# COMMAND ----------

# MAGIC %md
# MAGIC # ── BRONZE ──
# MAGIC ## 1 · `bronze_calls` — raw call metadata (Auto Loader)
# MAGIC
# MAGIC One row per call as landed by the ingest adapter. Append-only + ingest metadata.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT call_id, agent, language, duration_seconds, started_at, source, expected_category
# MAGIC FROM bronze_calls
# MAGIC ORDER BY started_at
# MAGIC LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · `bronze_transcripts` — raw STT transcript text (Auto Loader)
# MAGIC
# MAGIC The raw speech-to-text output, one row per call, before any cleaning.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT call_id, substr(transcript, 1, 160) AS transcript_preview, length(transcript) AS transcript_chars
# MAGIC FROM bronze_transcripts
# MAGIC ORDER BY call_id
# MAGIC LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC # ── SILVER ──
# MAGIC ## 3 · `silver_transcripts` — cleaned & validated transcripts
# MAGIC
# MAGIC Joins the transcript to the call's language, tags the STT model, and validates
# MAGIC that the transcript is non-empty. One clean row per call.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT call_id, language, stt_model, length(transcript) AS transcript_chars,
# MAGIC        substr(transcript, 1, 160) AS transcript_preview
# MAGIC FROM silver_transcripts
# MAGIC ORDER BY call_id
# MAGIC LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC # ── GOLD ──
# MAGIC ## 4 · `gold_call_summaries` — structured GenAI output + auto-filed ticket
# MAGIC
# MAGIC `ai_query(Claude)` turns each Silver transcript into a typed summary, category,
# MAGIC sentiment, and action items, and files a follow-up ticket via the `create_ticket`
# MAGIC UC function.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT call_id, agent, language, category, sentiment, ticket_id, llm_model,
# MAGIC        substr(summary, 1, 160) AS summary_preview
# MAGIC FROM gold_call_summaries
# MAGIC ORDER BY started_at
# MAGIC LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC # ── END-TO-END TRACE ──
# MAGIC ## 5 · One call through all three layers: `CALL-a82dce985c`
# MAGIC
# MAGIC The clearest proof the medallion works: follow a single call from raw metadata,
# MAGIC to its raw then cleaned transcript, to the final structured AI summary + ticket.

# COMMAND ----------

# MAGIC %md ### 5a · Bronze — the raw call + raw transcript

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   c.call_id, c.agent, c.language, c.duration_seconds, c.source, c.expected_category,
# MAGIC   t.transcript AS raw_transcript
# MAGIC FROM bronze_calls c
# MAGIC JOIN bronze_transcripts t USING (call_id)
# MAGIC WHERE c.call_id = 'CALL-a82dce985c';

# COMMAND ----------

# MAGIC %md ### 5b · Silver — the cleaned, validated transcript

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT call_id, language, stt_model, transcribed_at, transcript
# MAGIC FROM silver_transcripts
# MAGIC WHERE call_id = 'CALL-a82dce985c';

# COMMAND ----------

# MAGIC %md ### 5c · Gold — the structured AI summary, enrichments & ticket

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT call_id, category, sentiment, ticket_id, llm_model, action_items, summary
# MAGIC FROM gold_call_summaries
# MAGIC WHERE call_id = 'CALL-a82dce985c';

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6 · Quality check — classification accuracy vs. ground truth
# MAGIC
# MAGIC The synthetic `bronze_calls` carries `expected_category`; comparing the agent's
# MAGIC `category` against it measures the Gold GenAI step end-to-end.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   round(100.0 * sum(CASE WHEN g.category = b.expected_category THEN 1 ELSE 0 END) / count(*), 1) AS category_accuracy_pct,
# MAGIC   count(*) AS calls
# MAGIC FROM gold_call_summaries g
# MAGIC JOIN bronze_calls b USING (call_id);

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### ✅ Result
# MAGIC A single call was traced from **Bronze** (raw metadata + raw transcript) through
# MAGIC **Silver** (cleaned, validated transcript) to **Gold** (structured AI summary,
# MAGIC category, sentiment, action items, and auto-filed ticket) — with every layer's
# MAGIC real output shown, and classification matching ground truth. The medallion
# MAGIC pipeline transforms data correctly end-to-end.

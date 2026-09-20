-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 03 · Layer 4 — GenAI Summarization Agent (Claude) + Layer 1 Gold
-- MAGIC
-- MAGIC Runs **Claude (`databricks-claude-sonnet-4-5`)** over every Silver transcript
-- MAGIC with `ai_query`, producing a structured, **language-independent** summary
-- MAGIC (English output for RO & EN calls), and files a follow-up ticket via the
-- MAGIC `create_ticket` **Unity Catalog function tool**. Result lands in Gold.

-- COMMAND ----------

-- MAGIC %md ## Agent tool: create_ticket (Unity Catalog function)

-- COMMAND ----------

CREATE OR REPLACE FUNCTION salt_bank_voicescribe.voicescribe.create_ticket(call_id STRING, category STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Agent tool: create a Jira-style follow-up ticket, returns ticket id'
RETURN concat('SB-', upper(substr(sha2(concat(call_id, category), 256), 1, 8)));

-- COMMAND ----------

-- MAGIC %md ## Summarize all transcripts → Gold

-- COMMAND ----------

INSERT OVERWRITE salt_bank_voicescribe.voicescribe.gold_call_summaries
  (call_id, agent, language, started_at, duration_seconds, summary, category,
   sentiment, action_items, ticket_id, llm_model, summarized_at)
WITH scored AS (
  SELECT s.call_id, b.agent, s.language, b.started_at, b.duration_seconds,
         ai_query(
           'databricks-claude-sonnet-4-5',
           concat(
             'You are VoiceScribe for Salt Bank. Summarize this support call ',
             'transcript (Romanian or English). Respond ONLY with a JSON object ',
             'with keys: summary (2-3 sentences in English), category (one of ',
             'card_lost, fraud_dispute, loan_inquiry, app_technical, account_closure, ',
             'other), sentiment (positive, neutral, negative), action_items (array ',
             'of short strings). No markdown. Transcript: ', s.transcript)
         ) AS js
  FROM salt_bank_voicescribe.voicescribe.silver_transcripts s
  JOIN salt_bank_voicescribe.voicescribe.bronze_calls b USING (call_id)
),
parsed AS (
  SELECT call_id, agent, language, started_at, duration_seconds,
         from_json(
           regexp_replace(js, '(?s)^[^{]*(\\{.*\\})[^}]*$', '$1'),
           'STRUCT<summary:STRING, category:STRING, sentiment:STRING, action_items:ARRAY<STRING>>'
         ) AS r
  FROM scored
)
SELECT call_id, agent, language, started_at, duration_seconds,
       r.summary,
       coalesce(r.category,'other') AS category,
       coalesce(r.sentiment,'neutral') AS sentiment,
       r.action_items,
       salt_bank_voicescribe.voicescribe.create_ticket(call_id, coalesce(r.category,'other')) AS ticket_id,
       'databricks-claude-sonnet-4-5' AS llm_model,
       current_timestamp()
FROM parsed;

-- COMMAND ----------

-- MAGIC %md ## Evidence: category accuracy vs. synthetic ground truth

-- COMMAND ----------

SELECT round(100.0*sum(CASE WHEN g.category=b.expected_category THEN 1 ELSE 0 END)/count(*),1) AS category_accuracy_pct
FROM salt_bank_voicescribe.voicescribe.gold_call_summaries g
JOIN salt_bank_voicescribe.voicescribe.bronze_calls b USING (call_id);

-- COMMAND ----------

SELECT call_id, language, category, sentiment, ticket_id, summary
FROM salt_bank_voicescribe.voicescribe.gold_call_summaries
ORDER BY started_at
LIMIT 10;

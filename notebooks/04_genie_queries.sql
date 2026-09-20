-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 04 · Layer 5 — Genie Analytics Queries (validated)
-- MAGIC
-- MAGIC These are the natural-language questions the VoiceScribe Genie space answers,
-- MAGIC with the SQL Genie generates. All validated against the live Gold table.

-- COMMAND ----------
-- MAGIC %md ### "How many calls did we have by category?"
SELECT category, count(*) AS calls
FROM salt_bank_voicescribe.voicescribe.gold_call_summaries
GROUP BY category ORDER BY calls DESC;

-- COMMAND ----------
-- MAGIC %md ### "What is the average call duration by agent, in minutes?"
SELECT agent, round(avg(duration_seconds)/60.0, 1) AS avg_minutes
FROM salt_bank_voicescribe.voicescribe.gold_call_summaries
GROUP BY agent ORDER BY avg_minutes DESC;

-- COMMAND ----------
-- MAGIC %md ### "Show the share of negative-sentiment calls by language."
SELECT language,
       round(100.0*sum(CASE WHEN sentiment='negative' THEN 1 ELSE 0 END)/count(*), 1) AS pct_negative
FROM salt_bank_voicescribe.voicescribe.gold_call_summaries
GROUP BY language;

-- COMMAND ----------
-- MAGIC %md ### "Which agent handled the most account closure calls?"
SELECT agent, count(*) AS closures
FROM salt_bank_voicescribe.voicescribe.gold_call_summaries
WHERE category = 'account_closure'
GROUP BY agent ORDER BY closures DESC LIMIT 1;

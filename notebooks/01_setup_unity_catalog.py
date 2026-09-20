# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Layer 1 — Unity Catalog & Medallion Setup
# MAGIC
# MAGIC Creates the governed VoiceScribe medallion in Unity Catalog:
# MAGIC
# MAGIC | Layer  | Object | Contents |
# MAGIC |--------|--------|----------|
# MAGIC | Bronze | `raw_audio` (Volume) + `bronze_calls` | raw call audio + call metadata |
# MAGIC | Silver | `silver_transcripts` | STT output, one row per call |
# MAGIC | Gold   | `gold_call_summaries` | structured AI summary + enrichments + ticket id |
# MAGIC
# MAGIC **Synthetic data only.** Governed by Unity Catalog (lineage + access control).

# COMMAND ----------

CATALOG = "salt_bank_voicescribe"
SCHEMA = "voicescribe"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
print(f"Using {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md ## Bronze — call metadata

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS bronze_calls (
    call_id            STRING  NOT NULL,
    agent              STRING,
    from_number        STRING,
    to_number          STRING,
    language           STRING,             -- 'ro' | 'en'
    duration_seconds   INT,
    started_at         TIMESTAMP,
    recording_uri      STRING,             -- path in raw_audio volume / synthetic transcript
    source             STRING,             -- 'twilio' | 'synthetic'
    expected_category  STRING,             -- ground-truth label (synthetic eval only)
    expected_sentiment STRING,
    ingested_at        TIMESTAMP DEFAULT current_timestamp()
)
COMMENT 'Bronze: raw call metadata as ingested from Twilio/synthetic adapter'
""")

# COMMAND ----------

# MAGIC %md ## Silver — transcripts (output of Layer 3 STT)

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS silver_transcripts (
    call_id          STRING NOT NULL,
    language         STRING,
    transcript       STRING,              -- full STT transcript
    stt_model        STRING,              -- e.g. 'whisper-large-v3'
    transcribed_at   TIMESTAMP DEFAULT current_timestamp()
)
COMMENT 'Silver: speech-to-text transcripts, one row per call'
""")

# COMMAND ----------

# MAGIC %md ## Gold — structured AI summaries (output of Layer 4 agent)

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS gold_call_summaries (
    call_id          STRING NOT NULL,
    agent            STRING,
    language         STRING,
    started_at       TIMESTAMP,
    duration_seconds INT,
    summary          STRING,              -- concise language-independent summary
    category         STRING,              -- card_lost | fraud_dispute | loan_inquiry | app_technical | account_closure
    sentiment        STRING,              -- positive | neutral | negative
    action_items     ARRAY<STRING>,
    ticket_id        STRING,              -- created via UC function tool
    llm_model        STRING,              -- e.g. 'databricks-claude-...'
    summarized_at    TIMESTAMP DEFAULT current_timestamp()
)
COMMENT 'Gold: structured, analytics-ready call summaries + enrichments'
""")

# COMMAND ----------

# MAGIC %md ## Load synthetic Bronze data
# MAGIC In production, the ingest adapter writes Bronze. For the demo we load the
# MAGIC committed synthetic metadata so the pipeline can run end-to-end.

# COMMAND ----------

import json, os

# Path to the repo's synthetic metadata (adjust if running from a Repo/Workspace path)
CANDIDATES = [
    "/Workspace/Repos/xintia.gyenge@databricks.com/salt-bank-voicescribe/data/synthetic/calls_metadata.jsonl",
    os.path.expanduser("~/salt-bank-voicescribe/data/synthetic/calls_metadata.jsonl"),
    "./data/synthetic/calls_metadata.jsonl",
]
meta_path = next((p for p in CANDIDATES if os.path.exists(p)), None)

if meta_path:
    rows = [json.loads(l) for l in open(meta_path, encoding="utf-8") if l.strip()]
    df = spark.createDataFrame(rows).select(
        "call_id", "agent", "from_number", "to_number", "language",
        "duration_seconds", "started_at", "recording_uri", "source",
        "expected_category", "expected_sentiment",
    )
    df.write.mode("overwrite").saveAsTable("bronze_calls")
    print(f"Loaded {df.count()} synthetic calls into bronze_calls from {meta_path}")
else:
    print("Synthetic metadata file not found on this path; upload data/synthetic/ "
          "to the workspace or run generate_synthetic_calls.py first.")

# COMMAND ----------

display(spark.sql("SELECT language, count(*) AS calls FROM bronze_calls GROUP BY language"))

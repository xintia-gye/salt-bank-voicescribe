"""
VoiceScribe — Lakeflow Declarative Pipeline (Layer 1)

Bronze -> Silver -> Gold medallion as a real, schedulable Lakeflow pipeline
(serverless). Publishes to Unity Catalog: salt_bank_voicescribe.voicescribe.

- Bronze  (pl_bronze_calls)      : raw call metadata from the UC Volume JSONL
- Silver  (pl_silver_transcripts): transcript text files joined to metadata (STT stand-in)
- Gold    (pl_gold_call_summaries): Claude summaries via ai_query + auto-filed ticket

Table names are prefixed `pl_` so this pipeline coexists with the notebook-built
tables (bronze_calls / silver_transcripts / gold_call_summaries) without clashing.
"""
import dlt
from pyspark.sql import functions as F

VOLUME = "/Volumes/salt_bank_voicescribe/voicescribe/raw_audio"

SUMMARY_PROMPT = (
    "You are VoiceScribe for Salt Bank. Summarize this support call transcript "
    "(Romanian or English). Respond ONLY with a JSON object with keys: "
    "summary (2-3 sentences in English), category (one of card_lost, fraud_dispute, "
    "loan_inquiry, app_technical, account_closure, other), sentiment (positive, "
    "neutral, negative), action_items (array of short strings). No markdown. Transcript: "
)
SUMMARY_SCHEMA = "STRUCT<summary:STRING, category:STRING, sentiment:STRING, action_items:ARRAY<STRING>>"


@dlt.table(
    name="pl_bronze_calls",
    comment="Bronze: raw call metadata ingested from the UC Volume (Lakeflow)",
)
def pl_bronze_calls():
    return (
        spark.read.format("json")
        .load(f"{VOLUME}/calls_metadata.jsonl")
        .withColumn("started_at", F.to_timestamp("started_at"))
        .withColumn("ingested_at", F.current_timestamp())
    )


@dlt.table(
    name="pl_silver_transcripts",
    comment="Silver: STT transcripts (text files) joined to call metadata (Lakeflow)",
)
@dlt.expect_or_drop("has_transcript", "length(transcript) > 0")
def pl_silver_transcripts():
    transcripts = (
        spark.read.format("text")
        .option("wholetext", "true")
        .load(f"{VOLUME}/transcripts/")
        .withColumn("call_id", F.regexp_extract(F.col("_metadata.file_path"), r"(CALL-[a-f0-9]+)", 1))
        .withColumnRenamed("value", "transcript")
    )
    bronze = dlt.read("pl_bronze_calls").select("call_id", "language")
    return (
        transcripts.join(bronze, "call_id", "inner")
        .withColumn("stt_model", F.lit("whisper-large-v3"))
        .withColumn("transcribed_at", F.current_timestamp())
        .select("call_id", "language", "transcript", "stt_model", "transcribed_at")
    )


@dlt.table(
    name="pl_gold_call_summaries",
    comment="Gold: Claude structured summaries + auto-filed ticket (Lakeflow, Layer 4 in-pipeline)",
)
def pl_gold_call_summaries():
    silver = dlt.read("pl_silver_transcripts")
    bronze = dlt.read("pl_bronze_calls").select(
        "call_id", "agent", "started_at", "duration_seconds"
    )
    scored = (
        silver.join(bronze, "call_id", "inner")
        .withColumn(
            "js",
            F.expr(f"ai_query('databricks-claude-sonnet-4-5', concat('{SUMMARY_PROMPT}', transcript))"),
        )
        .withColumn("j", F.regexp_replace("js", r"(?s)^[^{]*(\{.*\})[^}]*$", "$1"))
        .withColumn("r", F.from_json("j", SUMMARY_SCHEMA))
    )
    return (
        scored.withColumn("summary", F.col("r.summary"))
        .withColumn("category", F.coalesce(F.col("r.category"), F.lit("other")))
        .withColumn("sentiment", F.coalesce(F.col("r.sentiment"), F.lit("neutral")))
        .withColumn("action_items", F.col("r.action_items"))
        .withColumn(
            "ticket_id",
            F.expr("salt_bank_voicescribe.voicescribe.create_ticket(call_id, category)"),
        )
        .withColumn("llm_model", F.lit("databricks-claude-sonnet-4-5"))
        .withColumn("summarized_at", F.current_timestamp())
        .select(
            "call_id", "agent", "language", "started_at", "duration_seconds",
            "summary", "category", "sentiment", "action_items", "ticket_id",
            "llm_model", "summarized_at",
        )
    )

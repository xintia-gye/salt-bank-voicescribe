# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Layer 3 — Speech-to-Text (Whisper)
# MAGIC
# MAGIC Transcribes call audio (Romanian & English) into the **Silver** layer using
# MAGIC OpenAI **Whisper** (`whisper-large-v3`). Whisper is language-independent and
# MAGIC auto-detects RO/EN.
# MAGIC
# MAGIC Two modes:
# MAGIC - **Model Serving** — call a deployed Whisper endpoint (production).
# MAGIC - **In-notebook** — run `faster-whisper` locally on the synthetic `.wav` files
# MAGIC   (works on serverless/GPU; used to generate evidence).
# MAGIC
# MAGIC If no audio is present (transcripts-only synthetic mode), the committed
# MAGIC transcripts already populate Silver (see notebook 01); this notebook then
# MAGIC simply verifies them.

# COMMAND ----------

# MAGIC %pip install faster-whisper
# MAGIC %restart_python

# COMMAND ----------

CATALOG, SCHEMA = "salt_bank_voicescribe", "voicescribe"
AUDIO_DIR = f"/Volumes/{CATALOG}/{SCHEMA}/raw_audio/audio"
STT_MODEL = "whisper-large-v3"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md ## Transcribe audio files with Whisper (if present)

# COMMAND ----------

import os, glob
from pyspark.sql import Row

audio_files = glob.glob(f"/Volumes/{CATALOG}/{SCHEMA}/raw_audio/audio/*.wav")
print(f"Found {len(audio_files)} audio files")

if audio_files:
    from faster_whisper import WhisperModel
    model = WhisperModel("large-v3", device="cpu", compute_type="int8")

    rows = []
    for path in audio_files:
        call_id = os.path.basename(path).replace(".wav", "")
        segments, info = model.transcribe(path)          # auto language detection
        text = " ".join(seg.text.strip() for seg in segments)
        rows.append(Row(call_id=call_id, language=info.language,
                        transcript=text, stt_model=STT_MODEL))

    (spark.createDataFrame(rows)
        .withColumn("transcribed_at", __import__("pyspark").sql.functions.current_timestamp())
        .write.mode("overwrite").saveAsTable("silver_transcripts"))
    print(f"Transcribed {len(rows)} calls into silver_transcripts")
else:
    print("No audio files present — using committed synthetic transcripts already "
          "loaded into silver_transcripts by notebook 01.")

# COMMAND ----------

# MAGIC %md ## Verify Silver

# COMMAND ----------

display(spark.sql("""
  SELECT language, count(*) AS calls, round(avg(length(transcript)),0) AS avg_len
  FROM silver_transcripts GROUP BY language ORDER BY language
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Production: calling a Whisper Model Serving endpoint
# MAGIC ```python
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC w = WorkspaceClient()
# MAGIC # audio bytes -> base64, POST to the whisper serving endpoint
# MAGIC resp = w.serving_endpoints.query(name="voicescribe-whisper-stt",
# MAGIC                                   inputs=[{"audio": b64_wav}])
# MAGIC transcript = resp.predictions[0]["text"]
# MAGIC ```

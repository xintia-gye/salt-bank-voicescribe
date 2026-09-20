-- Silver — cleaned transcripts, one row per call, enriched with the call's
-- language and tagged with the STT model. Validated: transcript must be present.
CREATE OR REFRESH MATERIALIZED VIEW silver_transcripts
COMMENT 'Silver: validated speech-to-text transcripts, one row per call'
AS
SELECT
  t.call_id,
  c.language,
  t.transcript,
  'whisper-large-v3'    AS stt_model,
  current_timestamp()   AS transcribed_at
FROM bronze_transcripts t
LEFT JOIN bronze_calls c USING (call_id)
WHERE t.transcript IS NOT NULL AND length(trim(t.transcript)) > 0;

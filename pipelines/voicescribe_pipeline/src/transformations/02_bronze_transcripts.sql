-- Bronze — raw speech-to-text transcripts, landed from the STT step.
-- In production this is written by the Whisper Model Serving step; here we
-- ingest the committed synthetic transcripts with Auto Loader.
CREATE OR REFRESH STREAMING TABLE bronze_transcripts
COMMENT 'Bronze: raw STT transcript text, one row per call (Auto Loader)'
AS
SELECT
  call_id,
  transcript,
  current_timestamp()   AS ingested_at,
  _metadata.file_path   AS _source_file
FROM STREAM read_files(
  '${landing_volume}/transcripts/',
  format => 'json',
  schemaHints => 'call_id STRING, transcript STRING'
);

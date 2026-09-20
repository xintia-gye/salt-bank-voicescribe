-- Bronze — raw call metadata, ingested from the landing volume with Auto Loader.
-- One row per call (Twilio- or synthetic-sourced). Append-only + ingest metadata.
CREATE OR REFRESH STREAMING TABLE bronze_calls
COMMENT 'Bronze: raw call metadata as landed by the ingest adapter (Auto Loader)'
CLUSTER BY (language)
AS
SELECT
  call_id,
  agent,
  from_number,
  to_number,
  language,                                    -- 'ro' | 'en'
  CAST(duration_seconds AS INT)   AS duration_seconds,
  CAST(started_at AS TIMESTAMP)   AS started_at,
  recording_uri,
  source,                                       -- 'twilio' | 'synthetic'
  expected_category,                            -- synthetic ground-truth (eval only)
  expected_sentiment,
  current_timestamp()             AS ingested_at,
  _metadata.file_path             AS _source_file
FROM STREAM read_files(
  '${landing_volume}/calls/',
  format => 'json',
  schemaHints => 'call_id STRING, agent STRING, from_number STRING, to_number STRING, language STRING, duration_seconds INT, started_at STRING, recording_uri STRING, source STRING, expected_category STRING, expected_sentiment STRING'
);

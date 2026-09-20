-- Gold — structured, analytics-ready call summaries (Layer 4 GenAI agent).
-- Runs Claude via ai_query over every silver transcript, parses the JSON into
-- typed columns, and files a follow-up ticket via the create_ticket UC function.
-- This is the table the app + Genie read.
CREATE OR REFRESH MATERIALIZED VIEW gold_call_summaries
COMMENT 'Gold: structured AI summary + enrichments + auto-filed ticket, one row per call'
CLUSTER BY (category)
AS
WITH scored AS (
  SELECT
    s.call_id, c.agent, s.language, c.started_at, c.duration_seconds,
    ai_query(
      '${llm_endpoint}',
      concat(
        'You are VoiceScribe for Salt Bank. Summarize this support call ',
        'transcript (Romanian or English). Respond ONLY with a JSON object ',
        'with keys: summary (2-3 sentences in English), category (one of ',
        'card_lost, fraud_dispute, loan_inquiry, app_technical, account_closure, ',
        'other), sentiment (positive, neutral, negative), action_items (array ',
        'of short strings). No markdown. Transcript: ', s.transcript)
    ) AS js
  FROM silver_transcripts s
  LEFT JOIN bronze_calls c USING (call_id)
),
parsed AS (
  SELECT
    call_id, agent, language, started_at, duration_seconds,
    from_json(
      regexp_replace(js, '(?s)^[^{]*(\\{.*\\})[^}]*$', '$1'),
      'STRUCT<summary:STRING, category:STRING, sentiment:STRING, action_items:ARRAY<STRING>>'
    ) AS r
  FROM scored
)
SELECT
  call_id,
  agent,
  language,
  started_at,
  duration_seconds,
  r.summary,
  coalesce(r.category, 'other')     AS category,
  coalesce(r.sentiment, 'neutral')  AS sentiment,
  r.action_items,
  salt_bank_voicescribe.voicescribe_pipeline.create_ticket(
    call_id, coalesce(r.category, 'other'))            AS ticket_id,
  '${llm_endpoint}'                 AS llm_model,
  current_timestamp()               AS summarized_at
FROM parsed;

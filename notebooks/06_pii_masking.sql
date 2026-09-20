-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 06 · Governance — Unity Catalog PII Masking (Layer 1)
-- MAGIC
-- MAGIC Dynamic **column masks** protect PII in the serving tables. Masks are keyed on
-- MAGIC `is_account_group_member('admins')`, so **admins see full data** and everyone
-- MAGIC else (the app's service principal, analysts, Genie users) sees masked data —
-- MAGIC enforced at query time, **regardless of tool** (app, Genie, SQL editor).
-- MAGIC
-- MAGIC This is a strong governance story for a bank: PII never leaves the governed
-- MAGIC environment unmasked for non-privileged consumers.

-- COMMAND ----------
-- MAGIC %md ## Mask functions

-- COMMAND ----------

-- Phone numbers: reveal only country code + last 2 digits, e.g. +40*******63
CREATE OR REPLACE FUNCTION salt_bank_voicescribe.voicescribe.mask_phone(p STRING)
RETURNS STRING
RETURN CASE
  WHEN is_account_group_member('admins') THEN p
  WHEN p IS NULL THEN NULL
  ELSE concat(substr(p, 1, 3), '*******', substr(p, length(p)-1, 2))
END;

-- Free text: redact runs of 4+ digits (card numbers, IBAN/account digits)
CREATE OR REPLACE FUNCTION salt_bank_voicescribe.voicescribe.redact_pii_text(t STRING)
RETURNS STRING
RETURN CASE
  WHEN is_account_group_member('admins') THEN t
  WHEN t IS NULL THEN NULL
  ELSE regexp_replace(t, '[0-9]{4,}', '[REDACTED]')
END;

-- COMMAND ----------
-- MAGIC %md ## Apply masks to the serving tables

-- COMMAND ----------

ALTER TABLE salt_bank_voicescribe.voicescribe.bronze_calls
  ALTER COLUMN from_number SET MASK salt_bank_voicescribe.voicescribe.mask_phone;
ALTER TABLE salt_bank_voicescribe.voicescribe.bronze_calls
  ALTER COLUMN to_number   SET MASK salt_bank_voicescribe.voicescribe.mask_phone;
ALTER TABLE salt_bank_voicescribe.voicescribe.silver_transcripts
  ALTER COLUMN transcript  SET MASK salt_bank_voicescribe.voicescribe.redact_pii_text;
ALTER TABLE salt_bank_voicescribe.voicescribe.gold_call_summaries
  ALTER COLUMN summary     SET MASK salt_bank_voicescribe.voicescribe.redact_pii_text;

-- COMMAND ----------
-- MAGIC %md ## Verify (non-admin sees masked; admin sees full)

-- COMMAND ----------

SELECT from_number FROM salt_bank_voicescribe.voicescribe.bronze_calls LIMIT 3;
-- non-admin → +40*******63 ; admin → full number

-- COMMAND ----------

SELECT table_name, column_name, mask_name
FROM salt_bank_voicescribe.information_schema.column_masks
WHERE table_schema = 'voicescribe' ORDER BY table_name;

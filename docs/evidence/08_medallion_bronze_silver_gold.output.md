# 08 · Bronze → Silver → Gold Walkthrough — executed output (text)

**Databricks job run** `153107346629968` (result `SUCCESS`) on the **bolt** workspace (`adb-984752964297111`), catalog `salt_bank_voicescribe.voicescribe_pipeline`. Captured 2026-09-22.

> This is a plain-text rendering of the **executed** notebook (`08_medallion_bronze_silver_gold.executed.ipynb`) — every ``` OUTPUT ``` block below is the real result Databricks produced when the notebook ran, not hand-written.

# 08 · Medallion Walkthrough — Bronze → Silver → Gold (with output)

This notebook **traces real data through every layer of the pipeline** so the
output cells prove the medallion transforms end-to-end — not just that rows exist,
but *what the data looks like* at each stage: raw call metadata (Bronze) → cleaned
transcript (Silver) → structured GenAI summary + ticket (Gold).

| | |
|---|---|
| Workspace | `adb-984752964297111` (bolt) |
| Catalog / schema | `salt_bank_voicescribe` / `voicescribe_pipeline` |
| Pipeline | `voicescribe-medallion` (`86e45489-d65a-440c-8c40-3831561a7f6a`) |
| Trace call | `CALL-a82dce985c` (followed through all three layers) |

> The committed output cells were produced by running this notebook on Databricks.
> Re-run against the live workspace to reproduce.

```sql
USE CATALOG salt_bank_voicescribe;
USE SCHEMA voicescribe_pipeline;
```

## Layer overview — rows at every stage

40 calls flow bronze → silver → gold with no rows dropped.

```sql
SELECT 'bronze_calls'        AS layer_table, 'Bronze' AS layer, count(*) AS rows FROM bronze_calls
UNION ALL SELECT 'bronze_transcripts', 'Bronze', count(*) FROM bronze_transcripts
UNION ALL SELECT 'silver_transcripts', 'Silver', count(*) FROM silver_transcripts
UNION ALL SELECT 'gold_call_summaries','Gold',   count(*) FROM gold_call_summaries
ORDER BY layer_table;
```
```text  (OUTPUT)
layer_table         | layer  | rows
--------------------+--------+-----
bronze_calls        | Bronze | 40  
bronze_transcripts  | Bronze | 40  
gold_call_summaries | Gold   | 40  
silver_transcripts  | Silver | 40
```

# ── BRONZE ──
## 1 · `bronze_calls` — raw call metadata (Auto Loader)

One row per call as landed by the ingest adapter. Append-only + ingest metadata.

```sql
SELECT call_id, agent, language, duration_seconds, started_at, source, expected_category
FROM bronze_calls
ORDER BY started_at
LIMIT 5;
```
```text  (OUTPUT)
call_id         | agent      | language | duration_seconds | started_at               | source    | expected_category
----------------+------------+----------+------------------+--------------------------+-----------+------------------
CALL-a82dce985c | E. Marin   | ro       | 284              | 2026-09-01T10:10:00.000Z | synthetic | card_lost        
CALL-00ce224f10 | C. Dumitru | ro       | 124              | 2026-09-02T02:09:00.000Z | synthetic | card_lost        
CALL-ed7b057e28 | M. Ionescu | en       | 212              | 2026-09-02T16:38:00.000Z | synthetic | loan_inquiry     
CALL-a5875e8b30 | C. Dumitru | ro       | 284              | 2026-09-03T13:49:00.000Z | synthetic | card_lost        
CALL-0651376088 | A. Popescu | en       | 371              | 2026-09-03T14:28:00.000Z | synthetic | card_lost
```

## 2 · `bronze_transcripts` — raw STT transcript text (Auto Loader)

The raw speech-to-text output, one row per call, before any cleaning.

```sql
SELECT call_id, substr(transcript, 1, 160) AS transcript_preview, length(transcript) AS transcript_chars
FROM bronze_transcripts
ORDER BY call_id
LIMIT 5;
```
```text  (OUTPUT)
call_id         | transcript_preview                                                                                                                                               | transcript_chars
----------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------+-----------------
CALL-00ce224f10 | AGENT: Salt Bank, bună ziua, cu ce vă pot ajuta?
CUSTOMER: Bună, mi-am pierdut cardul ieri și vreau să îl blochez.
AGENT: Îmi pare rău. Îl blochez imediat. Îmi  | 478             
CALL-0651376088 | AGENT: Salt Bank, good afternoon, how can I help?
CUSTOMER: Hi, I lost my card yesterday and I want to block it.
AGENT: I'm sorry to hear that. I can block it r | 494             
CALL-0bd5a12504 | AGENT: Salt Bank, cu ce vă pot ajuta?
CUSTOMER: Vreau să îmi închid contul, schimb banca.
AGENT: Îmi pare rău. Pot întreba motivul?
CUSTOMER: Prea multe comisio | 394             
CALL-0da43b1ebf | AGENT: Salt Bank, bună ziua, cu ce vă pot ajuta?
CUSTOMER: Bună, mi-am pierdut cardul ieri și vreau să îl blochez.
AGENT: Îmi pare rău. Îl blochez imediat. Îmi  | 478             
CALL-1216c888bd | AGENT: Bună dimineața, Salt Bank.
CUSTOMER: Aș vrea să știu dacă mă calific pentru un credit de 10.000 de euro.
AGENT: Pot face o verificare preliminară. Care e | 471
```

# ── SILVER ──
## 3 · `silver_transcripts` — cleaned & validated transcripts

Joins the transcript to the call's language, tags the STT model, and validates
that the transcript is non-empty. One clean row per call.

```sql
SELECT call_id, language, stt_model, length(transcript) AS transcript_chars,
       substr(transcript, 1, 160) AS transcript_preview
FROM silver_transcripts
ORDER BY call_id
LIMIT 5;
```
```text  (OUTPUT)
call_id         | language | stt_model        | transcript_chars | transcript_preview                                                                                                                                              
----------------+----------+------------------+------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------
CALL-00ce224f10 | ro       | whisper-large-v3 | 478              | AGENT: Salt Bank, bună ziua, cu ce vă pot ajuta?
CUSTOMER: Bună, mi-am pierdut cardul ieri și vreau să îl blochez.
AGENT: Îmi pare rău. Îl blochez imediat. Îmi 
CALL-0651376088 | en       | whisper-large-v3 | 494              | AGENT: Salt Bank, good afternoon, how can I help?
CUSTOMER: Hi, I lost my card yesterday and I want to block it.
AGENT: I'm sorry to hear that. I can block it r
CALL-0bd5a12504 | ro       | whisper-large-v3 | 394              | AGENT: Salt Bank, cu ce vă pot ajuta?
CUSTOMER: Vreau să îmi închid contul, schimb banca.
AGENT: Îmi pare rău. Pot întreba motivul?
CUSTOMER: Prea multe comisio
CALL-0da43b1ebf | ro       | whisper-large-v3 | 478              | AGENT: Salt Bank, bună ziua, cu ce vă pot ajuta?
CUSTOMER: Bună, mi-am pierdut cardul ieri și vreau să îl blochez.
AGENT: Îmi pare rău. Îl blochez imediat. Îmi 
CALL-1216c888bd | ro       | whisper-large-v3 | 471              | AGENT: Bună dimineața, Salt Bank.
CUSTOMER: Aș vrea să știu dacă mă calific pentru un credit de 10.000 de euro.
AGENT: Pot face o verificare preliminară. Care e
```

# ── GOLD ──
## 4 · `gold_call_summaries` — structured GenAI output + auto-filed ticket

`ai_query(Claude)` turns each Silver transcript into a typed summary, category,
sentiment, and action items, and files a follow-up ticket via the `create_ticket`
UC function.

```sql
SELECT call_id, agent, language, category, sentiment, ticket_id, llm_model,
       substr(summary, 1, 160) AS summary_preview
FROM gold_call_summaries
ORDER BY started_at
LIMIT 5;
```
```text  (OUTPUT)
call_id         | agent      | language | category     | sentiment | ticket_id   | llm_model                    | summary_preview                                                                                                                                                 
----------------+------------+----------+--------------+-----------+-------------+------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------
CALL-a82dce985c | E. Marin   | ro       | card_lost    | neutral   | SB-00A0C6AD | databricks-claude-sonnet-4-5 | Customer reported losing their card and requested it be blocked. Agent immediately blocked the card ending in 4471 and arranged for a replacement card to be sen
CALL-00ce224f10 | C. Dumitru | ro       | card_lost    | neutral   | SB-7BE259A7 | databricks-claude-sonnet-4-5 | Customer reported losing their card and requested it be blocked. Agent successfully blocked the card ending in 4471 and arranged for a replacement card to be se
CALL-ed7b057e28 | M. Ionescu | en       | loan_inquiry | positive  | SB-0BB04A8B | databricks-claude-sonnet-4-5 | Customer inquired about qualifying for a 10,000 euro personal loan for home renovation. Agent performed a soft check based on 2,500 monthly income and confirmed
CALL-a5875e8b30 | C. Dumitru | ro       | card_lost    | neutral   | SB-FDE72543 | databricks-claude-sonnet-4-5 | Customer reported losing their card and requested it be blocked. Agent successfully blocked the card ending in 4471 and arranged for a replacement card to be se
CALL-0651376088 | A. Popescu | en       | card_lost    | positive  | SB-6A4681CD | databricks-claude-sonnet-4-5 | Customer reported a lost card and requested it be blocked. Agent successfully blocked the card ending in 4471 and ordered a replacement to be delivered to the c
```

# ── END-TO-END TRACE ──
## 5 · One call through all three layers: `CALL-a82dce985c`

The clearest proof the medallion works: follow a single call from raw metadata,
to its raw then cleaned transcript, to the final structured AI summary + ticket.

### 5a · Bronze — the raw call + raw transcript

```sql
SELECT
  c.call_id, c.agent, c.language, c.duration_seconds, c.source, c.expected_category,
  t.transcript AS raw_transcript
FROM bronze_calls c
JOIN bronze_transcripts t USING (call_id)
WHERE c.call_id = 'CALL-a82dce985c';
```
```text  (OUTPUT)
call_id         | agent    | language | duration_seconds | source    | expected_category | raw_transcript                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
----------------+----------+----------+------------------+-----------+-------------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
CALL-a82dce985c | E. Marin | ro       | 284              | synthetic | card_lost         | AGENT: Salt Bank, bună ziua, cu ce vă pot ajuta?
CUSTOMER: Bună, mi-am pierdut cardul ieri și vreau să îl blochez.
AGENT: Îmi pare rău. Îl blochez imediat. Îmi confirmați numele și data nașterii?
CUSTOMER: Da, sunt Mihai D., născut pe 14 martie.
AGENT: Mulțumesc. Cardul care se termină în 4471 este acum blocat. Doriți un card nou?
CUSTOMER: Da, vă rog, la adresa de domiciliu.
AGENT: Gata. Ajunge în 3-5 zile lucrătoare. Mai pot ajuta cu ceva?
CUSTOMER: Nu, mulțumesc frumos.
```

### 5b · Silver — the cleaned, validated transcript

```sql
SELECT call_id, language, stt_model, transcribed_at, transcript
FROM silver_transcripts
WHERE call_id = 'CALL-a82dce985c';
```
```text  (OUTPUT)
call_id         | language | stt_model        | transcribed_at           | transcript                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   
----------------+----------+------------------+--------------------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
CALL-a82dce985c | ro       | whisper-large-v3 | 2026-09-22T12:16:15.696Z | AGENT: Salt Bank, bună ziua, cu ce vă pot ajuta?
CUSTOMER: Bună, mi-am pierdut cardul ieri și vreau să îl blochez.
AGENT: Îmi pare rău. Îl blochez imediat. Îmi confirmați numele și data nașterii?
CUSTOMER: Da, sunt Mihai D., născut pe 14 martie.
AGENT: Mulțumesc. Cardul care se termină în 4471 este acum blocat. Doriți un card nou?
CUSTOMER: Da, vă rog, la adresa de domiciliu.
AGENT: Gata. Ajunge în 3-5 zile lucrătoare. Mai pot ajuta cu ceva?
CUSTOMER: Nu, mulțumesc frumos.
```

### 5c · Gold — the structured AI summary, enrichments & ticket

```sql
SELECT call_id, category, sentiment, ticket_id, llm_model, action_items, summary
FROM gold_call_summaries
WHERE call_id = 'CALL-a82dce985c';
```
```text  (OUTPUT)
call_id         | category  | sentiment | ticket_id   | llm_model                    | action_items                                                                                                          | summary                                                                                                                                                                                                                   
----------------+-----------+-----------+-------------+------------------------------+-----------------------------------------------------------------------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
CALL-a82dce985c | card_lost | neutral   | SB-00A0C6AD | databricks-claude-sonnet-4-5 | ['Card ending in 4471 blocked', 'Replacement card ordered to home address', 'Delivery expected in 3-5 business days'] | Customer reported losing their card and requested it be blocked. Agent immediately blocked the card ending in 4471 and arranged for a replacement card to be sent to the customer's home address within 3-5 business days.
```

## 6 · Quality check — classification accuracy vs. ground truth

The synthetic `bronze_calls` carries `expected_category`; comparing the agent's
`category` against it measures the Gold GenAI step end-to-end.

```sql
SELECT
  round(100.0 * sum(CASE WHEN g.category = b.expected_category THEN 1 ELSE 0 END) / count(*), 1) AS category_accuracy_pct,
  count(*) AS calls
FROM gold_call_summaries g
JOIN bronze_calls b USING (call_id);
```
```text  (OUTPUT)
category_accuracy_pct | calls
----------------------+------
100.0                 | 40
```

---
### ✅ Result
A single call was traced from **Bronze** (raw metadata + raw transcript) through
**Silver** (cleaned, validated transcript) to **Gold** (structured AI summary,
category, sentiment, action items, and auto-filed ticket) — with every layer's
real output shown, and classification matching ground truth. The medallion
pipeline transforms data correctly end-to-end.

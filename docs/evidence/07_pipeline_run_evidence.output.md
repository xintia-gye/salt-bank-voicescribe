# 07 · Pipeline Run Evidence — executed output (text)

**Databricks job run** `221692384572973` (result `SUCCESS`) on the **bolt** workspace (`adb-984752964297111`). The notebook triggered its own fresh pipeline update `356db78f-…` which reached `COMPLETED`. Captured 2026-09-22.

> This is a plain-text rendering of the **executed** notebook (`07_pipeline_run_evidence.executed.ipynb`) — every ``` OUTPUT ``` block below is the real result Databricks produced when the notebook ran, not hand-written.

# 07 · Pipeline Run Evidence — the build works

This notebook **triggers the Lakeflow medallion pipeline end-to-end, waits for it
to finish, and queries every layer** so the output cells themselves are proof the
build runs cleanly — bronze → silver → gold, with the GenAI summarization agent
filling the Gold table.

| Pipeline | `voicescribe-medallion` |
|---|---|
| Pipeline ID | `86e45489-d65a-440c-8c40-3831561a7f6a` |
| Workspace | `adb-984752964297111` (bolt) |
| Catalog / schema | `salt_bank_voicescribe` / `voicescribe_pipeline` |
| Flows | `bronze_calls`, `bronze_transcripts`, `silver_transcripts`, `gold_call_summaries` |

> The **committed output** below (in the `%md` "Captured output" cells) was recorded
> from a real run on **2026-09-22** (update `acd51175-5803-42ac-95cd-5737b2affe1e`,
> state `COMPLETED`). Re-run the code cells to reproduce it against the live workspace.

## 1 · Trigger a fresh pipeline run

Kick off an update via the Pipelines API. The returned `update_id` is what we poll
and what the run log is keyed on.

```python
from databricks.sdk import WorkspaceClient

PIPELINE_ID = "86e45489-d65a-440c-8c40-3831561a7f6a"
w = WorkspaceClient()

started = w.pipelines.start_update(pipeline_id=PIPELINE_ID)
update_id = started.update_id
print(f"Started update {update_id} on pipeline {PIPELINE_ID}")
```
```text  (OUTPUT)
Started update 356db78f-69f8-459d-85bf-2196143d2ec5 on pipeline 86e45489-d65a-440c-8c40-3831561a7f6a
```

## 2 · Wait for the run to complete

Poll until the update reaches a terminal state. A clean build ends in `COMPLETED`.

```python
import time

TERMINAL = {"COMPLETED", "FAILED", "CANCELED"}
state = None
for _ in range(60):
    upd = w.pipelines.get_update(pipeline_id=PIPELINE_ID, update_id=update_id).update
    state = str(upd.state)
    print(f"update {update_id[:6]} -> {state}")
    if any(t in state for t in TERMINAL):
        break
    time.sleep(15)

assert "COMPLETED" in state, f"Pipeline did not complete cleanly: {state}"
print("\n✅ Pipeline completed cleanly.")
```
```text  (OUTPUT)
update 356db7 -> UpdateInfoState.CREATED
update 356db7 -> UpdateInfoState.WAITING_FOR_RESOURCES
update 356db7 -> UpdateInfoState.INITIALIZING
update 356db7 -> UpdateInfoState.RUNNING
update 356db7 -> UpdateInfoState.RUNNING
update 356db7 -> UpdateInfoState.RUNNING
update 356db7 -> UpdateInfoState.RUNNING
update 356db7 -> UpdateInfoState.COMPLETED

✅ Pipeline completed cleanly.
```

### Captured output — run lifecycle & flow log (2026-09-22, update `acd511`)
```
2026-09-22T11:57:02.271Z INFO Update acd511 is RUNNING.
2026-09-22T11:57:02.705Z INFO Flow '...bronze_calls' is STARTING.
2026-09-22T11:57:09.722Z INFO Flow '...bronze_calls' is RUNNING.
2026-09-22T11:57:10.520Z INFO Flow '...bronze_transcripts' is STARTING.
2026-09-22T11:57:11.215Z INFO Flow '...bronze_transcripts' is RUNNING.
2026-09-22T11:57:16.746Z INFO Flow '...bronze_calls' has COMPLETED.
2026-09-22T11:57:16.955Z INFO Flow '...bronze_transcripts' has COMPLETED.
2026-09-22T11:57:17.069Z INFO Flow '...silver_transcripts' is PLANNING.
2026-09-22T11:57:23.419Z INFO Flow '...silver_transcripts' planned as COMPLETE_RECOMPUTE.
2026-09-22T11:57:23.802Z INFO Flow '...silver_transcripts' is RUNNING.
2026-09-22T11:57:28.786Z INFO Flow '...silver_transcripts' has COMPLETED.
2026-09-22T11:57:28.808Z INFO Flow '...gold_call_summaries' is PLANNING.
2026-09-22T11:57:33.306Z INFO Flow '...gold_call_summaries' planned as COMPLETE_RECOMPUTE.
2026-09-22T11:57:33.434Z INFO Flow '...gold_call_summaries' is RUNNING.
2026-09-22T11:58:01.068Z INFO Flow '...gold_call_summaries' has COMPLETED.
2026-09-22T11:58:01.243Z INFO Update acd511 is COMPLETED.
```
All four flows `COMPLETED`; total wall time ≈ 59s on serverless.

## 3 · Verify every medallion layer materialized

A row per layer proves data flowed bronze → silver → gold with no drops.

```sql
USE CATALOG salt_bank_voicescribe;
USE SCHEMA voicescribe_pipeline;

SELECT 'bronze_calls'        AS layer_table, count(*) AS rows FROM bronze_calls
UNION ALL SELECT 'bronze_transcripts',  count(*) FROM bronze_transcripts
UNION ALL SELECT 'silver_transcripts',  count(*) FROM silver_transcripts
UNION ALL SELECT 'gold_call_summaries', count(*) FROM gold_call_summaries;
```
```text  (OUTPUT)
layer_table         | rows
--------------------+-----
bronze_calls        | 40  
bronze_transcripts  | 40  
silver_transcripts  | 40  
gold_call_summaries | 40
```

### Captured output
| layer_table | rows |
|---|---|
| bronze_calls | 40 |
| bronze_transcripts | 40 |
| silver_transcripts | 40 |
| gold_call_summaries | 40 |

40 calls in → 40 structured summaries out. No rows lost across the medallion.

## 4 · Gold layer — GenAI summaries the app + Genie read

Sample the structured output produced by `ai_query(Claude)` plus the auto-filed
`create_ticket()` UC-function ticket.

```sql
SELECT call_id, agent, language, category, sentiment, ticket_id, summary
FROM gold_call_summaries
ORDER BY started_at
LIMIT 3;
```
```text  (OUTPUT)
call_id         | agent      | language | category     | sentiment | ticket_id   | summary                                                                                                                                                                                                                                                                 
----------------+------------+----------+--------------+-----------+-------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
CALL-a82dce985c | E. Marin   | ro       | card_lost    | neutral   | SB-00A0C6AD | Customer reported losing their card and requested it be blocked. Agent immediately blocked the card ending in 4471 and arranged for a replacement card to be sent to the customer's home address within 3-5 business days.                                              
CALL-00ce224f10 | C. Dumitru | ro       | card_lost    | neutral   | SB-7BE259A7 | Customer reported losing their card and requested it be blocked. Agent successfully blocked the card ending in 4471 and arranged for a replacement card to be sent to the customer's home address within 3-5 business days.                                             
CALL-ed7b057e28 | M. Ionescu | en       | loan_inquiry | positive  | SB-0BB04A8B | Customer inquired about qualifying for a 10,000 euro personal loan for home renovation. Agent performed a soft check based on 2,500 monthly income and confirmed likely qualification with an indicative 8.9% APR, sending a pre-offer to the customer's app for review.
```

### Captured output
| call_id | agent | lang | category | sentiment | ticket_id | summary |
|---|---|---|---|---|---|---|
| CALL-a82dce985c | E. Marin | ro | card_lost | neutral | SB-00A0C6AD | Customer reported losing their card and requested it be blocked. Agent blocked the card ending 4471 and arranged a replacement to the home address within 3-5 business days. |
| CALL-00ce224f10 | C. Dumitru | ro | card_lost | neutral | SB-7BE259A7 | Customer reported losing their card and requested it be blocked. Agent blocked the card ending 4471 and arranged a replacement within 3-5 business days. |
| CALL-ed7b057e28 | M. Ionescu | en | loan_inquiry | positive | SB-0BB04A8B | Customer inquired about a €10,000 personal loan for renovation. Agent ran a soft check on €2,500 income, confirmed likely qualification at an indicative 8.9% APR, and sent a pre-offer to the app. |

RO and EN transcripts both summarized in English; every row got a `category`,
`sentiment`, and a `SB-…` ticket.

## 5 · Category distribution

```sql
SELECT category, count(*) AS calls
FROM gold_call_summaries
GROUP BY category
ORDER BY calls DESC;
```
```text  (OUTPUT)
category        | calls
----------------+------
card_lost       | 13   
account_closure | 7    
loan_inquiry    | 7    
fraud_dispute   | 7    
app_technical   | 6
```

### Captured output
| category | calls |
|---|---|
| card_lost | 13 |
| loan_inquiry | 7 |
| fraud_dispute | 7 |
| account_closure | 7 |
| app_technical | 6 |

## 6 · Quality check — classification accuracy vs. ground truth

The synthetic `bronze_calls` carries an `expected_category` label. Comparing the
agent's `category` against it measures the GenAI step end-to-end.

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

### Captured output
| category_accuracy_pct | calls |
|---|---|
| 100.0 | 40 |

On this run the summarization agent classified **40/40** calls to match the
synthetic ground truth.

---
### ✅ Result
The pipeline was **triggered live**, all four flows `COMPLETED`, all four layers
materialized (40 rows each), the GenAI Gold step produced structured summaries +
tickets, and classification matched ground truth. The build works.

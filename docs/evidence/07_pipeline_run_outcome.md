# Pipeline Run Outcome — `07_pipeline_run_evidence.py`

Rendered outcome of running the evidence notebook end-to-end against the live
**bolt** workspace (`adb-984752964297111`), so reviewers can see the result without
opening Databricks.

| | |
|---|---|
| Pipeline | `voicescribe-medallion` |
| Pipeline ID | `86e45489-d65a-440c-8c40-3831561a7f6a` |
| Update | `acd51175-5803-42ac-95cd-5737b2affe1e` |
| Date | 2026-09-22 |
| Final state | **COMPLETED** (all flows) |
| Catalog / schema | `salt_bank_voicescribe` / `voicescribe_pipeline` |

---

## Step 1–2 · Trigger + wait for completion

```
Started update acd51175-5803-42ac-95cd-5737b2affe1e on pipeline 86e45489…
update acd511 -> RUNNING
update acd511 -> RUNNING
update acd511 -> COMPLETED

✅ Pipeline completed cleanly.
```

Flow log (all four flows `COMPLETED`, ≈59s wall time on serverless — full log in
[`07_pipeline_rerun_log.txt`](07_pipeline_rerun_log.txt)):

```
11:57:02  Update acd511 is RUNNING.
11:57:16  Flow bronze_calls has COMPLETED.
11:57:16  Flow bronze_transcripts has COMPLETED.
11:57:28  Flow silver_transcripts has COMPLETED.
11:58:01  Flow gold_call_summaries has COMPLETED.
11:58:01  Update acd511 is COMPLETED.
```

## Step 3 · Every medallion layer materialized

| layer_table | rows |
|---|---|
| bronze_calls | 40 |
| bronze_transcripts | 40 |
| silver_transcripts | 40 |
| gold_call_summaries | 40 |

40 calls in → 40 structured summaries out. No rows lost across the medallion.

## Step 4 · Gold layer — GenAI summaries the app + Genie read

| call_id | agent | lang | category | sentiment | ticket_id | summary |
|---|---|---|---|---|---|---|
| CALL-a82dce985c | E. Marin | ro | card_lost | neutral | SB-00A0C6AD | Customer reported losing their card and requested it be blocked. Agent blocked the card ending 4471 and arranged a replacement to the home address within 3-5 business days. |
| CALL-00ce224f10 | C. Dumitru | ro | card_lost | neutral | SB-7BE259A7 | Customer reported losing their card and requested it be blocked. Agent blocked the card ending 4471 and arranged a replacement within 3-5 business days. |
| CALL-ed7b057e28 | M. Ionescu | en | loan_inquiry | positive | SB-0BB04A8B | Customer inquired about a €10,000 personal loan for renovation. Agent ran a soft check on €2,500 income, confirmed likely qualification at an indicative 8.9% APR, and sent a pre-offer to the app. |

RO and EN transcripts both summarized in English; every row got a `category`,
`sentiment`, and a `SB-…` ticket.

## Step 5 · Category distribution

| category | calls |
|---|---|
| card_lost | 13 |
| loan_inquiry | 7 |
| fraud_dispute | 7 |
| account_closure | 7 |
| app_technical | 6 |

## Step 6 · Quality check — classification accuracy vs. ground truth

| category_accuracy_pct | calls |
|---|---|
| 100.0 | 40 |

The summarization agent classified **40/40** calls to match the synthetic
`expected_category` ground truth.

---

## ✅ Result

The pipeline was **triggered live**, all four flows reached `COMPLETED`, all four
layers materialized (40 rows each), the GenAI Gold step produced structured
summaries + auto-filed tickets, and classification matched ground truth. **The
build works end-to-end.**

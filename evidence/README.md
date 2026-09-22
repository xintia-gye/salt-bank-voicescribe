# Evidence — Salt Bank VoiceScribe

Proof that the build **actually ran**, mapped to the required evidence checklist.
Everything here was captured **live** from the Databricks workspace
`adb-984752964297111` ("bolt"), catalog `salt_bank_voicescribe`, on 2026-09-22.
Data is synthetic; the runs, queries, model output, and Genie answers are real.

| # | Required | Where it is |
|---|----------|-------------|
| 1 | **Committed notebook outputs** showing the build ran | [`notebook_outputs/`](notebook_outputs/) — executed `.ipynb` **with output cells** (`07_pipeline_run_evidence`, `08_medallion_bronze_silver_gold`), their raw Databricks HTML exports, and a cell-by-cell text proof (`11_notebook_execution_proof.txt`) |
| 2 | **Screenshots** of each Databricks surface/layer & key outputs | [`Summary and Output screenshots.pdf`](Summary%20and%20Output%20screenshots.pdf) and [`Salt Bank VoiceScribe — Execution Evidence.pdf`](Salt%20Bank%20VoiceScribe%20—%20Execution%20Evidence.pdf) |
| 3 | **Validation/test results** — metrics, model output, integration checks | [`logs_and_queries/`](logs_and_queries/): pipeline run log (`04`, `09`), query results (`02`), transcript→summary model output (`05`, `10`), Genie integration (`03`), app/API integration (`06`), health check (`01`). **Metric: 100% category accuracy vs. ground truth over 40 calls.** |
| 4 | **3–5 min screen recording** of the end-to-end flow | ⏳ `screen_recording.mp4` — **to be added by the builder** (see note below) |
| 5 | **README** — what's implemented, how to run, deployed vs. illustrative | Root [`../README.md`](../README.md) + the "Deployed vs. illustrative" table there |
| 6 | **BUILD.md** — workflow, AI tools/prompts, key decisions | Root [`../BUILD.md`](../BUILD.md) |

## Headline proof (all captured live)

- **Pipeline ran:** Lakeflow update `356db78f` → `COMPLETED`; a second, newly-created
  pipeline `voicescribe-medallion-demo` (`6010b3d7…`), update `3bd8e45b` → `COMPLETED`.
- **Row counts (bronze→silver→gold):** 40 / 40 / 40 / 40 — no rows dropped.
- **Model output:** RO transcript `CALL-a82dce985c` → English summary + `SB-00A0C6AD`
  ticket, `llm_model = databricks-claude-sonnet-4-5`.
- **Genie:** "How many calls are there by category?" → generated SQL → returned rows
  (`card_lost 13, account_closure 7, fraud_dispute 7, loan_inquiry 7, app_technical 6`).
- **Quality metric:** 100% category accuracy vs. synthetic ground truth (40 calls).
- **App integration:** live `/api/health` = `{status: ok, lakebase_available: true}`.

## Note on the screen recording (item 4)

This is the one artifact that must be recorded by a person. Suggested 4-minute flow is
in [`../docs/DEMO_RUNBOOK.md`](../docs/DEMO_RUNBOOK.md). Save the file here as
`evidence/screen_recording.mp4` before submitting.

# Architecture & Effie Submission Plan

The full architecture and Effie submission plan is maintained as a Google Doc:

- **Architecture & Effie Submission Plan:** https://docs.google.com/document/d/1niJnKFRscitkE2_rdDVvRvO4u_h0whtv6DXvwP4YA-M/edit
- **Demo Narrative & Executive Pitch:** https://docs.google.com/document/d/15WrAgORFe40QOpo5Z2jyKcYEVFTz5nVjGLVNzWlCQrU/edit

See the [README](../README.md) for the six-layer architecture summary and data flow.

## The six layers

1. **Lakeflow + Unity Catalog** — declarative Bronze→Silver→Gold pipeline, UC governance & lineage.
2. **Lakebase** — managed Postgres serving the operator app.
3. **ML** — Whisper speech-to-text on Model Serving (RO/EN).
4. **GenAI agent** — summarizes, extracts action items, files ticket via UC function.
5. **Genie** — natural-language analytics for supervisors.
6. **Databricks App** — React + FastAPI operator/supervisor site.

## Twilio

Pluggable ingestion: real `TwilioAdapter` (webhook) or `SyntheticAdapter` (default, replays `data/synthetic/`). No Twilio account required to run the repo.

# Synthetic data

**Synthetic only — no real customers, audio, or PII.**

- `calls_metadata.jsonl` — one row per synthetic call (call_id, agent, language, duration, ground-truth category/sentiment).
- `transcripts/<call_id>.txt` — Romanian/English transcript text used as STT stand-in.
- `audio/` — optional TTS-rendered `.wav` (only if generated with `--audio`).

Regenerate: `python ../generate_synthetic_calls.py --n 40`

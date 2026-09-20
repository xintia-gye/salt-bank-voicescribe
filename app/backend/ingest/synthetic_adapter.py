"""Synthetic-recording ingest adapter (default).

Replays the text-to-speech call metadata + transcripts shipped in
data/synthetic. Each POST returns the next unused synthetic call (round-robin),
so the demo can simulate "a new call just came in" with no Twilio account.
"""
from __future__ import annotations

import json
import os
import threading
import uuid

from ..config import get_settings
from .base import CallIngestPayload, IngestAdapter


class SyntheticAdapter(IngestAdapter):
    name = "synthetic"

    def __init__(self) -> None:
        self._dir = get_settings().synthetic_data_dir
        self._lock = threading.Lock()
        self._cursor = 0
        self._records = self._load()

    def _load(self) -> list[dict]:
        path = os.path.join(self._dir, "calls_metadata.jsonl")
        records: list[dict] = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        return records

    def _transcript_for(self, rec: dict) -> str | None:
        uri = rec.get("recording_uri", "")
        fname = os.path.basename(uri) if uri else f"{rec.get('call_id')}.txt"
        # transcripts live under data/synthetic/transcripts/
        candidate = os.path.join(self._dir, "transcripts", fname)
        if os.path.exists(candidate):
            with open(candidate, encoding="utf-8") as fh:
                return fh.read()
        return None

    def validate(self, *, url: str, form: dict[str, str], headers: dict[str, str]) -> None:
        # No signature to validate for synthetic replays.
        return None

    def parse(self, *, form: dict[str, str]) -> CallIngestPayload:
        # Allow the caller to target a specific synthetic call_id, else round-robin.
        target = form.get("call_id")
        rec: dict | None = None
        if self._records:
            if target:
                rec = next((r for r in self._records if r.get("call_id") == target), None)
            if rec is None:
                with self._lock:
                    rec = self._records[self._cursor % len(self._records)]
                    self._cursor += 1
        if rec is None:
            # No synthetic corpus available — fabricate a minimal call.
            rec = {
                "call_id": f"CALL-{uuid.uuid4().hex[:10]}",
                "agent": "Synthetic Agent",
                "from_number": "+40700000000",
                "to_number": "+40316300000",
                "language": "ro",
                "duration_seconds": 120,
                "started_at": None,
                "recording_uri": None,
            }
        payload = CallIngestPayload(
            call_id=rec.get("call_id", f"CALL-{uuid.uuid4().hex[:10]}"),
            agent=rec.get("agent"),
            from_number=rec.get("from_number"),
            to_number=rec.get("to_number"),
            language=rec.get("language"),
            duration_seconds=rec.get("duration_seconds"),
            started_at=rec.get("started_at"),
            recording_uri=rec.get("recording_uri"),
            source="synthetic",
            raw=dict(rec),
        )
        transcript = self._transcript_for(rec)
        if transcript:
            payload.raw["transcript"] = transcript
        return payload

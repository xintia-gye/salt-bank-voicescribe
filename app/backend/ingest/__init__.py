"""Pluggable call-ingestion adapters.

The customer has no Twilio account yet, so the default adapter replays the
synthetic recordings/transcripts shipped in data/synthetic. When a Twilio
account is provisioned, set INGEST_ADAPTER=twilio and the TwilioAdapter takes
over — same interface, real webhooks.
"""
from __future__ import annotations

from ..config import get_settings
from .base import CallIngestPayload, IngestAdapter
from .synthetic_adapter import SyntheticAdapter
from .twilio_adapter import TwilioAdapter


def get_adapter() -> IngestAdapter:
    s = get_settings()
    if s.ingest_adapter == "twilio":
        return TwilioAdapter()
    return SyntheticAdapter()


__all__ = [
    "CallIngestPayload",
    "IngestAdapter",
    "SyntheticAdapter",
    "TwilioAdapter",
    "get_adapter",
]

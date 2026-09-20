"""Twilio Voice recording-webhook adapter.

Parses a real Twilio recording status callback:
  CallSid, From, To, RecordingUrl, RecordingDuration, RecordingSid ...
and validates the X-Twilio-Signature header against TWILIO_AUTH_TOKEN.

In a full deployment this adapter would also download the recording from
RecordingUrl and drop the audio into a UC Volume for the STT pipeline; that
download is stubbed here (recording_uri points at Twilio's URL) so the demo
does not require live Twilio credentials.
"""
from __future__ import annotations

import datetime as _dt
import uuid

from ..config import get_settings
from .base import CallIngestPayload, IngestAdapter


class TwilioAdapter(IngestAdapter):
    name = "twilio"

    def __init__(self) -> None:
        self._auth_token = get_settings().twilio_auth_token

    def validate(self, *, url: str, form: dict[str, str], headers: dict[str, str]) -> None:
        if not self._auth_token:
            raise PermissionError(
                "TWILIO_AUTH_TOKEN is not set; cannot validate Twilio signature."
            )
        signature = headers.get("x-twilio-signature") or headers.get("X-Twilio-Signature")
        if not signature:
            raise PermissionError("Missing X-Twilio-Signature header.")
        # Lazy import so the dependency is only needed in twilio mode.
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(self._auth_token)
        if not validator.validate(url, form, signature):
            raise PermissionError("Invalid Twilio signature.")

    def parse(self, *, form: dict[str, str]) -> CallIngestPayload:
        call_sid = form.get("CallSid") or f"CALL-{uuid.uuid4().hex[:10]}"
        duration = form.get("RecordingDuration")
        recording_url = form.get("RecordingUrl")
        if recording_url and not recording_url.endswith(".wav"):
            recording_url = recording_url + ".wav"
        return CallIngestPayload(
            call_id=call_sid,
            agent=form.get("Agent") or None,
            from_number=form.get("From"),
            to_number=form.get("To"),
            language=form.get("Language") or None,
            duration_seconds=int(duration) if duration and duration.isdigit() else None,
            started_at=form.get("Timestamp") or _dt.datetime.utcnow().isoformat(),
            recording_uri=recording_url,
            source="twilio",
            raw=dict(form),
        )

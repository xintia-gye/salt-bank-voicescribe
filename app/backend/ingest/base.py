"""Adapter interface for call ingestion."""
from __future__ import annotations

import abc
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CallIngestPayload:
    """Normalised representation of one incoming call, ready for bronze_calls."""

    call_id: str
    agent: str | None
    from_number: str | None
    to_number: str | None
    language: str | None
    duration_seconds: int | None
    started_at: str | None
    recording_uri: str | None
    source: str  # "twilio" | "synthetic"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_public(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("raw", None)
        return d


class IngestAdapter(abc.ABC):
    """Common interface for turning a webhook / trigger into a CallIngestPayload."""

    name: str = "base"

    @abc.abstractmethod
    def validate(self, *, url: str, form: dict[str, str], headers: dict[str, str]) -> None:
        """Raise ValueError / PermissionError if the request is not authentic."""

    @abc.abstractmethod
    def parse(self, *, form: dict[str, str]) -> CallIngestPayload:
        """Build a normalised payload from the incoming request body."""

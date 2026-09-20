"""
VoiceScribe summarization agent (Layer 4).

Takes a call transcript (Romanian or English) and returns a structured,
language-independent summary using Claude on Databricks Model Serving
(`databricks-claude-sonnet-4-5`). Also exposes `create_ticket`, which is
registered as a Unity Catalog function tool so the agent can file a
Jira-style follow-up ticket — automating the manual step operators do today.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from typing import List

from databricks.sdk import WorkspaceClient

ENDPOINT = "databricks-claude-sonnet-4-5"
LLM_MODEL_LABEL = "databricks-claude-sonnet-4-5"

CATEGORIES = ["card_lost", "fraud_dispute", "loan_inquiry",
              "app_technical", "account_closure", "other"]

SYSTEM_PROMPT = (
    "You are VoiceScribe, an assistant for Salt Bank that summarizes customer "
    "support calls. Given a call transcript in Romanian or English, respond ONLY "
    "with a JSON object with keys: summary (a concise 2-3 sentence summary in "
    "English regardless of the call's language), category (one of: "
    "card_lost, fraud_dispute, loan_inquiry, app_technical, account_closure, other), "
    "sentiment (positive, neutral, or negative), action_items (array of short "
    "strings), needs_ticket (boolean, true when a follow-up task remains). "
    "No markdown, no prose, JSON only."
)


@dataclass
class CallSummary:
    call_id: str
    summary: str
    category: str
    sentiment: str
    action_items: List[str] = field(default_factory=list)
    needs_ticket: bool = False
    ticket_id: str | None = None
    llm_model: str = LLM_MODEL_LABEL


def _strip_json_fences(text: str) -> str:
    """Claude sometimes wraps JSON in ```json ... ``` fences."""
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    return text.strip()


def summarize_transcript(call_id: str, transcript: str,
                         client: WorkspaceClient | None = None) -> CallSummary:
    """Call Claude and parse the structured summary for one transcript."""
    client = client or WorkspaceClient()
    resp = client.serving_endpoints.query(
        name=ENDPOINT,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        max_tokens=500,
        temperature=0.1,
    )
    content = resp.choices[0].message.content
    data = json.loads(_strip_json_fences(content))

    category = data.get("category", "other")
    if category not in CATEGORIES:
        category = "other"

    return CallSummary(
        call_id=call_id,
        summary=data.get("summary", "").strip(),
        category=category,
        sentiment=data.get("sentiment", "neutral"),
        action_items=list(data.get("action_items", [])),
        needs_ticket=bool(data.get("needs_ticket", False)),
    )


def create_ticket(call_id: str, category: str, summary: str,
                  action_items: List[str]) -> str:
    """Create a Jira-style follow-up ticket and return its id.

    Registered as a Unity Catalog function so the agent can call it as a tool.
    In this demo it mints a deterministic ticket id and the id is persisted to
    Gold; a production version would POST to Jira / the internal ticketing API.
    """
    return f"SB-{uuid.uuid4().hex[:8].upper()}"


def to_gold_row(cs: CallSummary) -> dict:
    d = asdict(cs)
    d.pop("needs_ticket", None)
    return d

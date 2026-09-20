"""Genie Conversation API client (Layer 5 — supervisor analytics).

Wraps the Databricks Genie REST API so the app can ask natural-language
questions over the gold call-summary table and render the SQL + result table
+ narrative answer. Works with either a PAT (local) or the app's
service-principal OAuth token (production).

Env:
  GENIE_SPACE_ID   the Genie space to query (defaults to the VoiceScribe space)
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests

from .config import get_settings

_settings = get_settings()

DEFAULT_SPACE_ID = "01f1b52b26c11cacb12269806671aa8e"


def get_space_id() -> str:
    return os.environ.get("GENIE_SPACE_ID") or DEFAULT_SPACE_ID


def _auth_header() -> dict[str, str]:
    """Bearer token for the Genie API.

    Local dev: DATABRICKS_TOKEN. Production Databricks App: mint an OAuth token
    from the injected service-principal credentials via the SDK.
    """
    if _settings.token:
        return {"Authorization": f"Bearer {_settings.token}"}
    # OAuth service principal.
    from databricks.sdk.core import Config

    cfg = Config(
        host=_settings.host,
        client_id=_settings.client_id,
        client_secret=_settings.client_secret,
    )
    headers = cfg.authenticate()  # {'Authorization': 'Bearer ...'}
    return {"Authorization": headers["Authorization"]}


def _base() -> str:
    return f"{_settings.host}/api/2.0/genie/spaces/{get_space_id()}"


def _req(method: str, path: str, json_body: dict | None = None) -> dict[str, Any]:
    url = f"{_base()}{path}"
    resp = requests.request(
        method, url, headers=_auth_header(), json=json_body, timeout=60
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Genie API {resp.status_code}: {resp.text[:500]}")
    return resp.json() if resp.text else {}


def _poll_message(conversation_id: str, message_id: str,
                  timeout_s: int = 90) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while True:
        msg = _req(
            "GET", f"/conversations/{conversation_id}/messages/{message_id}"
        )
        status = msg.get("status")
        if status in ("COMPLETED", "FAILED", "CANCELLED",
                      "QUERY_RESULT_EXPIRED"):
            return msg
        if time.time() > deadline:
            msg["status"] = msg.get("status") or "TIMEOUT"
            return msg
        time.sleep(2)


def _fetch_query_result(conversation_id: str, message_id: str,
                        attachment_id: str) -> dict[str, Any]:
    data = _req(
        "GET",
        f"/conversations/{conversation_id}/messages/{message_id}"
        f"/attachments/{attachment_id}/query-result",
    )
    sr = data.get("statement_response", {})
    columns = [c["name"] for c in
               sr.get("manifest", {}).get("schema", {}).get("columns", [])]
    rows = sr.get("result", {}).get("data_array", []) or []
    return {"columns": columns, "rows": rows}


def _shape_message(conversation_id: str, message: dict) -> dict[str, Any]:
    """Turn a completed Genie message into a compact response for the UI."""
    out: dict[str, Any] = {
        "conversation_id": conversation_id,
        "message_id": message.get("id") or message.get("message_id"),
        "status": message.get("status"),
        "text": None,
        "sql": None,
        "query_description": None,
        "columns": [],
        "rows": [],
        "suggested_questions": [],
    }
    texts: list[str] = []
    for att in message.get("attachments", []) or []:
        if "text" in att and att["text"]:
            content = att["text"].get("content") if isinstance(att["text"], dict) else att["text"]
            if content:
                texts.append(content)
        if "query" in att and att["query"]:
            q = att["query"]
            out["sql"] = q.get("query")
            out["query_description"] = q.get("description")
            att_id = att.get("attachment_id")
            if att_id and out["status"] == "COMPLETED":
                try:
                    res = _fetch_query_result(
                        conversation_id, out["message_id"], att_id
                    )
                    out["columns"] = res["columns"]
                    out["rows"] = res["rows"]
                except Exception as exc:  # noqa: BLE001
                    out["query_description"] = (
                        (out["query_description"] or "")
                        + f"\n(result fetch failed: {exc})"
                    )
        if "suggested_questions" in att and att["suggested_questions"]:
            sq = att["suggested_questions"]
            qs = sq.get("questions") if isinstance(sq, dict) else sq
            if isinstance(qs, list):
                out["suggested_questions"].extend(
                    [q.get("question", q) if isinstance(q, dict) else q for q in qs]
                )
    out["text"] = "\n\n".join(texts) if texts else None
    return out


def ask(question: str, conversation_id: str | None = None) -> dict[str, Any]:
    """Ask a question (new conversation) or a follow-up (existing id)."""
    if conversation_id:
        started = _req(
            "POST",
            f"/conversations/{conversation_id}/messages",
            {"content": question},
        )
        message_id = started.get("message_id") or started.get("id") \
            or started.get("message", {}).get("id")
    else:
        started = _req("POST", "/start-conversation", {"content": question})
        conversation_id = started.get("conversation_id")
        message_id = started.get("message_id") \
            or started.get("message", {}).get("id")

    message = _poll_message(conversation_id, message_id)
    return _shape_message(conversation_id, message)

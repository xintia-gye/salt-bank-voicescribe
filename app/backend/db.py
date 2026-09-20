"""Databricks SQL warehouse access layer.

Uses the databricks-sql-connector against the Shared Endpoint warehouse.
Auth resolves in this order:
  1. DATABRICKS_TOKEN (personal access token) — typical for local dev.
  2. OAuth service principal (DATABRICKS_CLIENT_ID / _SECRET) via the SDK
     credential provider — typical inside a Databricks App.

Approval status is tracked in a small in-memory store (a stub for the demo;
in production this would be a Lakebase Postgres table). See approvals below.
"""
from __future__ import annotations

import json
import threading
from typing import Any

from databricks import sql as dbsql

from .config import get_settings

_settings = get_settings()

# --- Approval status stub (would be a Lakebase table in production) ---
_approvals: dict[str, dict[str, Any]] = {}
_approvals_lock = threading.Lock()


def _connect():
    """Open a short-lived connection to the SQL warehouse."""
    s = _settings
    kwargs: dict[str, Any] = {
        "server_hostname": s.host_hostname,
        "http_path": s.http_path,
        "catalog": s.catalog,
        "schema": s.schema,
    }
    if s.token:
        kwargs["access_token"] = s.token
    else:
        # OAuth service principal via the SDK credential provider.
        from databricks.sdk.core import Config, oauth_service_principal

        cfg = Config(
            host=s.host,
            client_id=s.client_id,
            client_secret=s.client_secret,
        )
        kwargs["credentials_provider"] = lambda: oauth_service_principal(cfg)
    return dbsql.connect(**kwargs)


def _rows_to_dicts(cursor) -> list[dict[str, Any]]:
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def query(statement: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(statement, params or None)
            if cur.description is None:
                return []
            return _rows_to_dicts(cur)


def execute(statement: str, params: list[Any] | None = None) -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(statement, params or None)


# --------------------------------------------------------------------------
# Normalisation helpers
# --------------------------------------------------------------------------
def _coerce_action_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except (ValueError, TypeError):
            pass
        return [value]
    return [str(value)]


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    """JSON-friendly output: ISO timestamps, parsed action_items, approval merge."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    if "action_items" in out:
        out["action_items"] = _coerce_action_items(out["action_items"])
    # merge approval status stub
    call_id = out.get("call_id")
    if call_id:
        with _approvals_lock:
            appr = _approvals.get(call_id)
        out["approval_status"] = (appr or {}).get("status", "pending")
        out["edited_summary"] = (appr or {}).get("edited_summary")
        out["approved_by"] = (appr or {}).get("approved_by")
        out["approved_at"] = (appr or {}).get("approved_at")
    return out


# --------------------------------------------------------------------------
# Domain queries
# --------------------------------------------------------------------------
_LIST_SQL = """
SELECT g.call_id, g.agent, g.language, g.started_at, g.duration_seconds,
       g.summary, g.category, g.sentiment, g.ticket_id, g.llm_model,
       g.summarized_at
FROM gold_call_summaries g
{where}
ORDER BY g.started_at DESC
"""


def list_calls(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for field in ("category", "language", "sentiment", "agent"):
        val = filters.get(field)
        if val:
            clauses.append(f"g.{field} = ?")
            params.append(val)
    search = filters.get("search")
    if search:
        clauses.append("(LOWER(g.summary) LIKE ? OR LOWER(g.call_id) LIKE ? "
                       "OR LOWER(g.ticket_id) LIKE ?)")
        like = f"%{search.lower()}%"
        params.extend([like, like, like])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = query(_LIST_SQL.format(where=where), params)
    return [_serialize(r) for r in rows]


_DETAIL_SQL = """
SELECT g.call_id, g.agent, g.language, g.started_at, g.duration_seconds,
       g.summary, g.category, g.sentiment, g.action_items, g.ticket_id,
       g.llm_model, g.summarized_at,
       s.transcript, s.stt_model, s.transcribed_at
FROM gold_call_summaries g
LEFT JOIN silver_transcripts s ON g.call_id = s.call_id
WHERE g.call_id = ?
"""


def get_call(call_id: str) -> dict[str, Any] | None:
    rows = query(_DETAIL_SQL, [call_id])
    if not rows:
        return None
    return _serialize(rows[0])


def get_filter_options() -> dict[str, list[str]]:
    rows = query(
        "SELECT DISTINCT category, language, sentiment, agent "
        "FROM gold_call_summaries"
    )
    opts = {"category": set(), "language": set(), "sentiment": set(), "agent": set()}
    for r in rows:
        for k in opts:
            if r.get(k):
                opts[k].add(r[k])
    return {k: sorted(v) for k, v in opts.items()}


def get_stats() -> dict[str, Any]:
    by_category = query(
        "SELECT category AS label, COUNT(*) AS value "
        "FROM gold_call_summaries GROUP BY category ORDER BY value DESC"
    )
    by_language = query(
        "SELECT language AS label, COUNT(*) AS value "
        "FROM gold_call_summaries GROUP BY language ORDER BY value DESC"
    )
    by_sentiment = query(
        "SELECT sentiment AS label, COUNT(*) AS value "
        "FROM gold_call_summaries GROUP BY sentiment ORDER BY value DESC"
    )
    avg_duration_by_agent = query(
        "SELECT agent AS label, ROUND(AVG(duration_seconds), 0) AS value, "
        "COUNT(*) AS calls FROM gold_call_summaries GROUP BY agent "
        "ORDER BY value DESC"
    )
    totals = query(
        "SELECT COUNT(*) AS total_calls, "
        "ROUND(AVG(duration_seconds), 0) AS avg_duration, "
        "COUNT(DISTINCT agent) AS agents, "
        "COUNT(DISTINCT ticket_id) AS tickets "
        "FROM gold_call_summaries"
    )

    def norm(rows):
        for r in rows:
            r["value"] = int(r["value"]) if r.get("value") is not None else 0
            if "calls" in r and r["calls"] is not None:
                r["calls"] = int(r["calls"])
        return rows

    return {
        "totals": totals[0] if totals else {},
        "by_category": norm(by_category),
        "by_language": norm(by_language),
        "by_sentiment": norm(by_sentiment),
        "avg_duration_by_agent": norm(avg_duration_by_agent),
    }


# --------------------------------------------------------------------------
# Approval stub
# --------------------------------------------------------------------------
def set_approval(call_id: str, status: str, edited_summary: str | None,
                 approved_by: str | None) -> dict[str, Any]:
    import datetime as _dt

    record = {
        "status": status,
        "edited_summary": edited_summary,
        "approved_by": approved_by or "operator",
        "approved_at": _dt.datetime.utcnow().isoformat() + "Z",
    }
    with _approvals_lock:
        _approvals[call_id] = record
    return record

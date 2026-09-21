"""Lakebase (managed Postgres, OLTP) access layer — Layer 2.

Backs the operator workflow: the approval / edit state for each call is
persisted in `voicescribe.call_summaries` on the `voicescribe-oltp` Lakebase
instance, so it survives app restarts and is shared across replicas (unlike
the previous in-memory stub).

Auth:
  * Databricks App (prod): the app's service principal is registered as a
    Postgres role on the instance; we mint a short-lived OAuth token via the
    SDK and use it as the Postgres password. PGHOST/PGUSER/PGDATABASE are read
    from env (injected by the Lakebase app resource) with sensible fallbacks.
  * Local dev: same flow using the CLI profile / DATABRICKS_TOKEN identity.

Tokens expire (~1h), so the pool is rebuilt on auth errors and refreshed
periodically. If Lakebase is unreachable or unconfigured, callers fall back to
the in-memory stub in db.py (demo mode) — the app never hard-fails on it.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

import requests

from .config import get_settings

_settings = get_settings()

# Lazy imports so the app still boots if psycopg isn't present locally.
try:
    import psycopg2  # type: ignore
    import psycopg2.pool  # type: ignore
    _HAVE_PG = True
except Exception:  # noqa: BLE001
    _HAVE_PG = False

_INSTANCE = os.environ.get("LAKEBASE_INSTANCE", "voicescribe-oltp")
_DBNAME = os.environ.get("PGDATABASE", "databricks_postgres")
_HOST = os.environ.get("PGHOST")  # injected by the Lakebase app resource
_PORT = int(os.environ.get("PGPORT", "5432"))
_PGUSER = os.environ.get("PGUSER")  # app SP client id in prod

_pool = None
_pool_created_at = 0.0
_lock = threading.Lock()
_TOKEN_TTL = 40 * 60  # rebuild pool every ~40 min (token lives ~1h)
_available = _HAVE_PG  # flips False on unrecoverable errors
_last_error: str | None = None if _HAVE_PG else "psycopg2 not importable"


def last_error() -> str | None:
    return _last_error


def _workspace_bearer() -> str | None:
    """Bearer token for the Databricks REST API (PAT locally, OAuth SP in app)."""
    if _settings.token:
        return _settings.token
    try:
        from databricks.sdk.core import Config

        cfg = Config(
            host=_settings.host,
            client_id=_settings.client_id,
            client_secret=_settings.client_secret,
        )
        auth = cfg.authenticate()  # {'Authorization': 'Bearer ...'}
        return auth["Authorization"].replace("Bearer ", "")
    except Exception as exc:  # noqa: BLE001
        global _last_error
        _last_error = f"workspace auth failed: {exc}"
        return None


def _resolve_host_user_token() -> tuple[str | None, str | None, str | None]:
    """Return (host, user, token) for the Postgres connection.

    Uses the Database REST API directly (not the SDK's w.database, which may be
    absent in older databricks-sdk builds shipped with the app):
      GET  /api/2.0/database/instances/{name}   -> read_write_dns
      POST /api/2.0/database/credentials        -> short-lived PG token
    In a Databricks App, PGHOST/PGUSER may be injected by a database resource
    and take precedence.
    """
    global _last_error
    host, user = _HOST, _PGUSER
    bearer = _workspace_bearer()
    if not bearer:
        return host, user, None

    base = _settings.host.rstrip("/")
    headers = {"Authorization": f"Bearer {bearer}",
               "Content-Type": "application/json"}
    try:
        if not host:
            r = requests.get(
                f"{base}/api/2.0/database/instances/{_INSTANCE}",
                headers=headers, timeout=30,
            )
            if r.status_code >= 400:
                _last_error = f"get instance {r.status_code}: {r.text[:200]}"
                return host, user, None
            host = r.json().get("read_write_dns")

        import uuid

        r = requests.post(
            f"{base}/api/2.0/database/credentials",
            headers=headers,
            json={"request_id": str(uuid.uuid4()),
                  "instance_names": [_INSTANCE]},
            timeout=30,
        )
        if r.status_code >= 400:
            _last_error = f"gen credential {r.status_code}: {r.text[:200]}"
            return host, user, None
        token = r.json().get("token")

        if not user:
            # In prod the app's SP client id is the Postgres role name; locally
            # fall back to the current user's email.
            user = _settings.client_id
            if not user:
                me = requests.get(f"{base}/api/2.0/preview/scim/v2/Me",
                                  headers=headers, timeout=30)
                if me.status_code < 400:
                    user = me.json().get("userName")
        return host, user, token
    except Exception as exc:  # noqa: BLE001
        _last_error = f"credential resolution failed: {exc}"
        print(f"[lakebase] {_last_error}")
        return host, user, None


def _build_pool():
    global _pool, _pool_created_at, _available
    if not _HAVE_PG:
        _available = False
        return None
    host, user, token = _resolve_host_user_token()
    if not (host and user and token):
        _available = False
        global _last_error
        if not _last_error:
            _last_error = (f"missing conn params host={bool(host)} "
                           f"user={bool(user)} token={bool(token)}")
        return None
    try:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            host=host,
            port=_PORT,
            dbname=_DBNAME,
            user=user,
            password=token,
            sslmode="require",
        )
        _pool_created_at = time.time()
        _available = True
        _last_error = None
        return _pool
    except Exception as exc:  # noqa: BLE001
        _last_error = f"pool build failed: {exc}"
        print(f"[lakebase] {_last_error}")
        _available = False
        return None


def _get_pool():
    global _pool
    with _lock:
        if _pool is None or (time.time() - _pool_created_at) > _TOKEN_TTL:
            if _pool is not None:
                try:
                    _pool.closeall()
                except Exception:  # noqa: BLE001
                    pass
                _pool = None
            _build_pool()
        return _pool


def is_available() -> bool:
    """Best-effort check; triggers a lazy connect."""
    return _get_pool() is not None


def _run(fn):
    """Run fn(cursor) with a pooled connection, one retry on auth/conn error."""
    for attempt in range(2):
        pool = _get_pool()
        if pool is None:
            raise RuntimeError("lakebase unavailable")
        conn = pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                return fn(cur)
        except Exception as exc:  # noqa: BLE001
            # Force a pool rebuild (likely expired token) and retry once.
            global _pool
            with _lock:
                try:
                    pool.putconn(conn, close=True)
                except Exception:  # noqa: BLE001
                    pass
                _pool = None
            conn = None
            if attempt == 1:
                raise exc
        finally:
            if conn is not None:
                try:
                    pool.putconn(conn)
                except Exception:  # noqa: BLE001
                    pass


def _norm_status(s: str | None) -> str:
    """Map the DB's default sync status to the UI's vocabulary."""
    if not s or s == "pending_review":
        return "pending"
    return s


# --------------------------------------------------------------------------
# Operations
# --------------------------------------------------------------------------
def get_status(call_id: str) -> dict[str, Any] | None:
    def _q(cur):
        cur.execute(
            "SELECT status, edited_summary, approved_by, approved_at "
            "FROM voicescribe.call_summaries WHERE call_id = %s",
            (call_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "status": _norm_status(row[0]),
            "edited_summary": row[1],
            "approved_by": row[2],
            "approved_at": row[3].isoformat() if row[3] else None,
        }
    return _run(_q)


def get_all_statuses() -> dict[str, dict[str, Any]]:
    def _q(cur):
        cur.execute(
            "SELECT call_id, status, edited_summary, approved_by, approved_at "
            "FROM voicescribe.call_summaries"
        )
        out: dict[str, dict[str, Any]] = {}
        for r in cur.fetchall():
            out[r[0]] = {
                "status": _norm_status(r[1]),
                "edited_summary": r[2],
                "approved_by": r[3],
                "approved_at": r[4].isoformat() if r[4] else None,
            }
        return out
    return _run(_q)


def set_status(call_id: str, status: str, edited_summary: str | None,
               approved_by: str | None) -> dict[str, Any]:
    def _q(cur):
        cur.execute(
            """
            INSERT INTO voicescribe.call_summaries
                (call_id, status, edited_summary, approved_by, approved_at, updated_at)
            VALUES (%s, %s, %s, %s, now(), now())
            ON CONFLICT (call_id) DO UPDATE SET
                status = EXCLUDED.status,
                edited_summary = EXCLUDED.edited_summary,
                approved_by = EXCLUDED.approved_by,
                approved_at = EXCLUDED.approved_at,
                updated_at = now()
            RETURNING status, edited_summary, approved_by, approved_at
            """,
            (call_id, status, edited_summary, approved_by or "operator"),
        )
        row = cur.fetchone()
        return {
            "status": _norm_status(row[0]),
            "edited_summary": row[1],
            "approved_by": row[2],
            "approved_at": row[3].isoformat() if row[3] else None,
        }
    return _run(_q)

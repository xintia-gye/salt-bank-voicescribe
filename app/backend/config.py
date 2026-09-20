"""Runtime configuration and environment detection for VoiceScribe backend.

Supports two auth modes transparently:
  * Databricks App (production): a service principal is injected via
    DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET (OAuth). The SQL connector
    uses the SDK credential provider.
  * Local dev: a personal access token in DATABRICKS_TOKEN (or a CLI profile).

Never hardcode secrets. Everything comes from the environment / .env file.
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

# Load a local .env if present (no-op in production where env is injected).
load_dotenv()


def _normalize_host(raw: str) -> str:
    """Return the workspace URL with an https:// scheme.

    In a Databricks App, DATABRICKS_HOST may be injected as a bare hostname
    (no scheme); locally it usually already has https://.
    """
    h = (raw or "").strip().rstrip("/")
    if h and not h.startswith("http"):
        h = "https://" + h
    return h


class Settings:
    # --- Databricks workspace ---
    host: str = _normalize_host(os.environ.get("DATABRICKS_HOST", ""))
    token: str | None = os.environ.get("DATABRICKS_TOKEN") or None
    warehouse_id: str = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
    catalog: str = os.environ.get("DATABRICKS_CATALOG", "salt_bank_voicescribe")
    schema: str = os.environ.get("DATABRICKS_SCHEMA", "voicescribe")

    # OAuth service-principal creds (injected in a Databricks App).
    client_id: str | None = os.environ.get("DATABRICKS_CLIENT_ID") or None
    client_secret: str | None = os.environ.get("DATABRICKS_CLIENT_SECRET") or None

    # --- Ingestion ---
    ingest_adapter: str = os.environ.get("INGEST_ADAPTER", "synthetic").lower()
    twilio_auth_token: str | None = os.environ.get("TWILIO_AUTH_TOKEN") or None

    @property
    def synthetic_data_dir(self) -> str:
        # Explicit override wins.
        env = os.environ.get("SYNTHETIC_DATA_DIR")
        if env:
            return env
        # Search likely locations relative to this file and the cwd. In local
        # dev the corpus lives at <repo>/data/synthetic (one level above app/);
        # in a deployed App the app root is the source root, so we also bundle
        # a copy at <app_root>/data/synthetic.
        here = os.path.dirname(__file__)  # .../backend
        app_root = os.path.dirname(here)  # .../app  (source root in prod)
        repo_root = os.path.dirname(app_root)
        candidates = [
            os.path.join(app_root, "data", "synthetic"),
            os.path.join(repo_root, "data", "synthetic"),
            os.path.join(os.getcwd(), "data", "synthetic"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                return c
        return candidates[0]

    @property
    def is_databricks_app(self) -> bool:
        return bool(os.environ.get("DATABRICKS_APP_NAME"))

    @property
    def http_path(self) -> str:
        return f"/sql/1.0/warehouses/{self.warehouse_id}"

    @property
    def host_hostname(self) -> str:
        """Bare hostname (no scheme) as the SQL connector expects."""
        h = self.host
        if h.startswith("https://"):
            h = h[len("https://"):]
        elif h.startswith("http://"):
            h = h[len("http://"):]
        return h.rstrip("/")

    @property
    def db_configured(self) -> bool:
        return bool(self.host and self.warehouse_id and (self.token or self.client_id))


@lru_cache
def get_settings() -> Settings:
    return Settings()

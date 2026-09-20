#!/usr/bin/env bash
# One-shot local launcher for the VoiceScribe app.
# Requires network (installs from PyPI/npm). Run from the app/ directory.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Refreshing Databricks OAuth token into .env (bolt profile)"
TOKEN=$(databricks auth token --profile=bolt | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
# rewrite the DATABRICKS_TOKEN line in .env
if [ -f .env ]; then
  grep -v '^DATABRICKS_TOKEN=' .env > .env.tmp && mv .env.tmp .env
else
  cat > .env <<EOF
DATABRICKS_HOST=https://adb-984752964297111.11.azuredatabricks.net
DATABRICKS_WAREHOUSE_ID=148ccb90800933a1
DATABRICKS_CATALOG=salt_bank_voicescribe
DATABRICKS_SCHEMA=voicescribe
INGEST_ADAPTER=synthetic
EOF
fi
echo "DATABRICKS_TOKEN=$TOKEN" >> .env

echo "==> Backend: venv + deps"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r backend/requirements.txt

echo "==> Frontend: deps + build"
( cd frontend && npm install && npm run build )

echo "==> Starting server on http://localhost:8000 (serves API + built UI)"
.venv/bin/uvicorn backend.main:app --port 8000

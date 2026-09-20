# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Layer 2 — Lakebase (operational store) sync
# MAGIC
# MAGIC Lakebase (managed Postgres, OLTP) serves the operator App with low-latency
# MAGIC reads/writes: summary records + the operator workflow (status, approvals).
# MAGIC This notebook creates the operational table and syncs it from Gold.
# MAGIC
# MAGIC **Instance:** `voicescribe-oltp` (PG 16) · **DB:** `databricks_postgres` ·
# MAGIC **Schema/table:** `voicescribe.call_summaries`

# COMMAND ----------

# MAGIC %pip install psycopg2-binary
# MAGIC %restart_python

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import psycopg2

INSTANCE = "voicescribe-oltp"
w = WorkspaceClient()

inst = w.database.get_database_instance(name=INSTANCE)
cred = w.database.generate_database_credential(instance_names=[INSTANCE])
user = w.current_user.me().user_name

conn = psycopg2.connect(
    host=inst.read_write_dns, port=5432, dbname="databricks_postgres",
    user=user, password=cred.token, sslmode="require",
)
conn.autocommit = True
cur = conn.cursor()

# COMMAND ----------

# MAGIC %md ## Create operational schema + table

# COMMAND ----------

cur.execute("""
CREATE SCHEMA IF NOT EXISTS voicescribe;
CREATE TABLE IF NOT EXISTS voicescribe.call_summaries (
    call_id           TEXT PRIMARY KEY,
    agent             TEXT,
    language          TEXT,
    started_at        TIMESTAMPTZ,
    duration_seconds  INT,
    summary           TEXT,
    category          TEXT,
    sentiment         TEXT,
    action_items      TEXT,
    ticket_id         TEXT,
    status            TEXT DEFAULT 'pending_review',
    approved_by       TEXT,
    approved_at       TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_cs_category ON voicescribe.call_summaries (category);
CREATE INDEX IF NOT EXISTS ix_cs_status   ON voicescribe.call_summaries (status);
""")

# COMMAND ----------

# MAGIC %md ## Sync Gold → Lakebase

# COMMAND ----------

gold = spark.sql("""
  SELECT call_id, agent, language, cast(started_at AS string) AS started_at,
         duration_seconds, summary, category, sentiment,
         concat_ws(' | ', action_items) AS action_items, ticket_id
  FROM salt_bank_voicescribe.voicescribe.gold_call_summaries
""").collect()

for r in gold:
    cur.execute("""
        INSERT INTO voicescribe.call_summaries
          (call_id, agent, language, started_at, duration_seconds, summary,
           category, sentiment, action_items, ticket_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (call_id) DO UPDATE SET
          summary=EXCLUDED.summary, category=EXCLUDED.category,
          sentiment=EXCLUDED.sentiment, action_items=EXCLUDED.action_items,
          ticket_id=EXCLUDED.ticket_id, updated_at=now()
    """, (r.call_id, r.agent, r.language, r.started_at, r.duration_seconds,
          r.summary, r.category, r.sentiment, r.action_items, r.ticket_id))

print(f"Synced {len(gold)} rows to Lakebase")

# COMMAND ----------

cur.execute("SELECT status, count(*) FROM voicescribe.call_summaries GROUP BY status")
print(cur.fetchall())

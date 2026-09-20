import { useEffect, useState } from "react";
import { api, CallSummary, FilterOptions } from "../api";
import CallDetail from "./CallDetail";
import {
  CategoryBadge,
  LangBadge,
  SentimentBadge,
  StatusBadge,
  fmtDuration,
} from "./badges";

const EMPTY: FilterOptions = {
  category: [],
  language: [],
  sentiment: [],
  agent: [],
};

export default function CallsView() {
  const [opts, setOpts] = useState<FilterOptions>(EMPTY);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [rows, setRows] = useState<CallSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    api.filters().then(setOpts).catch(() => {});
  }, []);

  function load() {
    setLoading(true);
    setErr(null);
    api
      .calls(filters)
      .then(setRows)
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }

  useEffect(load, [JSON.stringify(filters)]);

  function setF(key: string, val: string) {
    setFilters((f) => ({ ...f, [key]: val }));
  }

  const activeFilters = Object.values(filters).some((v) => v);

  return (
    <div className="container">
      <div className="filters">
        <input
          placeholder="Search summary, call id, ticket…"
          value={filters.search || ""}
          onChange={(e) => setF("search", e.target.value)}
        />
        <Select
          label="Category"
          value={filters.category}
          options={opts.category}
          onChange={(v) => setF("category", v)}
        />
        <Select
          label="Language"
          value={filters.language}
          options={opts.language}
          onChange={(v) => setF("language", v)}
        />
        <Select
          label="Sentiment"
          value={filters.sentiment}
          options={opts.sentiment}
          onChange={(v) => setF("sentiment", v)}
        />
        <Select
          label="Agent"
          value={filters.agent}
          options={opts.agent}
          onChange={(v) => setF("agent", v)}
        />
        {activeFilters && (
          <button className="clear" onClick={() => setFilters({})}>
            Clear
          </button>
        )}
        <span className="count">{rows.length} calls</span>
      </div>

      {err && <div className="banner">Backend error: {err}</div>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Call ID</th>
              <th>Agent</th>
              <th>Lang</th>
              <th>Category</th>
              <th>Sentiment</th>
              <th>Duration</th>
              <th>Ticket</th>
              <th>Summary</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.call_id} onClick={() => setSelected(r.call_id)}>
                <td className="mono">{r.call_id}</td>
                <td>{r.agent || "—"}</td>
                <td>
                  <LangBadge value={r.language} />
                </td>
                <td>
                  <CategoryBadge value={r.category} />
                </td>
                <td>
                  <SentimentBadge value={r.sentiment} />
                </td>
                <td>{fmtDuration(r.duration_seconds)}</td>
                <td className="mono">{r.ticket_id || "—"}</td>
                <td className="summary-cell">
                  {(r.summary || "").slice(0, 120)}
                  {(r.summary || "").length > 120 ? "…" : ""}
                </td>
                <td>
                  <StatusBadge value={r.approval_status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="state">Loading calls…</div>}
        {!loading && rows.length === 0 && !err && (
          <div className="state">No calls match these filters.</div>
        )}
      </div>

      {selected && (
        <CallDetail
          callId={selected}
          onClose={() => setSelected(null)}
          onChanged={load}
        />
      )}
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value?: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <select value={value || ""} onChange={(e) => onChange(e.target.value)}>
      <option value="">{label}: all</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o.replace(/_/g, " ")}
        </option>
      ))}
    </select>
  );
}

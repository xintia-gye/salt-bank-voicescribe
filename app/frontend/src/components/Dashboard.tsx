import { useEffect, useState } from "react";
import { api, StatBar, Stats } from "../api";
import { fmtDuration } from "./badges";

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch((e) => setErr(String(e)));
  }, []);

  if (err)
    return (
      <div className="container">
        <div className="banner">Backend error: {err}</div>
      </div>
    );
  if (!stats)
    return (
      <div className="container">
        <div className="state">Loading dashboard…</div>
      </div>
    );

  const t = stats.totals;

  return (
    <div className="container">
      <div className="tiles">
        <Tile num={t.total_calls ?? 0} lbl="Total calls" />
        <Tile num={fmtDuration(t.avg_duration ?? 0)} lbl="Avg call duration" />
        <Tile num={t.agents ?? 0} lbl="Agents" />
        <Tile num={t.tickets ?? 0} lbl="Tickets filed" />
      </div>

      <div className="charts">
        <BarChart title="Calls by category" data={stats.by_category} />
        <BarChart title="Calls by language" data={stats.by_language} />
        <BarChart title="Sentiment breakdown" data={stats.by_sentiment} />
        <BarChart
          title="Avg duration by agent (sec)"
          data={stats.avg_duration_by_agent}
          durationStyle
          fmt={(v) => `${v}s`}
        />
      </div>
    </div>
  );
}

function Tile({ num, lbl }: { num: number | string; lbl: string }) {
  return (
    <div className="tile">
      <div className="num">{num}</div>
      <div className="lbl">{lbl}</div>
    </div>
  );
}

function BarChart({
  title,
  data,
  durationStyle,
  fmt,
}: {
  title: string;
  data: StatBar[];
  durationStyle?: boolean;
  fmt?: (v: number) => string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="chart-card">
      <h3>{title}</h3>
      {data.map((d) => (
        <div className="bar-row" key={d.label}>
          <div className="lab" title={d.label}>
            {(d.label || "—").replace(/_/g, " ")}
          </div>
          <div className="bar-track">
            <div
              className={`bar-fill${durationStyle ? " dur" : ""}`}
              style={{ width: `${(d.value / max) * 100}%` }}
            />
          </div>
          <div className="bar-val">{fmt ? fmt(d.value) : d.value}</div>
        </div>
      ))}
      {data.length === 0 && <div className="state">No data.</div>}
    </div>
  );
}

export function SentimentBadge({ value }: { value: string | null }) {
  const v = (value || "").toLowerCase();
  const cls = v === "positive" ? "pos" : v === "negative" ? "neg" : "neu";
  return <span className={`badge ${cls}`}>{value || "—"}</span>;
}

export function CategoryBadge({ value }: { value: string | null }) {
  if (!value) return <span className="badge neu">—</span>;
  return <span className="badge cat">{value.replace(/_/g, " ")}</span>;
}

export function LangBadge({ value }: { value: string | null }) {
  if (!value) return <span className="badge neu">—</span>;
  return <span className="badge lang">{value}</span>;
}

export function StatusBadge({ value }: { value?: string }) {
  const v = value || "pending";
  return <span className={`badge status-${v}`}>{v}</span>;
}

export function fmtDuration(sec: number | null): string {
  if (sec == null) return "—";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

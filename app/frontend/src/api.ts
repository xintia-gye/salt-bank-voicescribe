export interface CallSummary {
  call_id: string;
  agent: string | null;
  language: string | null;
  started_at: string | null;
  duration_seconds: number | null;
  summary: string | null;
  category: string | null;
  sentiment: string | null;
  ticket_id: string | null;
  llm_model: string | null;
  summarized_at: string | null;
  approval_status?: string;
  edited_summary?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
}

export interface CallDetail extends CallSummary {
  action_items: string[];
  transcript: string | null;
  stt_model: string | null;
  transcribed_at: string | null;
}

export interface FilterOptions {
  category: string[];
  language: string[];
  sentiment: string[];
  agent: string[];
}

export interface StatBar {
  label: string;
  value: number;
  calls?: number;
}

export interface Stats {
  totals: {
    total_calls?: number;
    avg_duration?: number;
    agents?: number;
    tickets?: number;
  };
  by_category: StatBar[];
  by_language: StatBar[];
  by_sentiment: StatBar[];
  avg_duration_by_agent: StatBar[];
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  filters: () => fetch("/api/filters").then((r) => json<FilterOptions>(r)),
  stats: () => fetch("/api/stats").then((r) => json<Stats>(r)),
  calls: (params: Record<string, string>) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v))
    ).toString();
    return fetch(`/api/calls${qs ? `?${qs}` : ""}`).then((r) =>
      json<CallSummary[]>(r)
    );
  },
  call: (id: string) =>
    fetch(`/api/calls/${encodeURIComponent(id)}`).then((r) =>
      json<CallDetail>(r)
    ),
  approve: (id: string, action: string, editedSummary?: string) =>
    fetch(`/api/calls/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        edited_summary: editedSummary,
        approved_by: "operator",
      }),
    }).then((r) => json<Record<string, unknown>>(r)),
};

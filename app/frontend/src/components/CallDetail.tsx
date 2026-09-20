import { useEffect, useState } from "react";
import { api, CallDetail as Detail } from "../api";
import {
  CategoryBadge,
  LangBadge,
  SentimentBadge,
  StatusBadge,
  fmtDate,
  fmtDuration,
} from "./badges";

export default function CallDetail({
  callId,
  onClose,
  onChanged,
}: {
  callId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [data, setData] = useState<Detail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setData(null);
    setErr(null);
    setEditing(false);
    api
      .call(callId)
      .then((d) => {
        setData(d);
        setDraft(d.edited_summary || d.summary || "");
      })
      .catch((e) => setErr(String(e)));
  }, [callId]);

  async function doApprove() {
    setSaving(true);
    try {
      await api.approve(callId, "approve");
      const d = await api.call(callId);
      setData(d);
      onChanged();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function doSaveEdit() {
    setSaving(true);
    try {
      await api.approve(callId, "edit", draft);
      const d = await api.call(callId);
      setData(d);
      setEditing(false);
      onChanged();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <button className="close" onClick={onClose}>
            ×
          </button>
          <h2>{callId}</h2>
          {data && (
            <div className="chips">
              <CategoryBadge value={data.category} />
              <LangBadge value={data.language} />
              <SentimentBadge value={data.sentiment} />
              <StatusBadge value={data.approval_status} />
            </div>
          )}
        </div>
        <div className="drawer-body">
          {err && <div className="banner">{err}</div>}
          {!data && !err && <div className="state">Loading…</div>}
          {data && (
            <>
              <div className="section">
                <div className="meta-grid">
                  <div>
                    <span>Agent</span>
                    {data.agent || "—"}
                  </div>
                  <div>
                    <span>Started</span>
                    {fmtDate(data.started_at)}
                  </div>
                  <div>
                    <span>Duration</span>
                    {fmtDuration(data.duration_seconds)}
                  </div>
                  <div>
                    <span>Model</span>
                    {data.llm_model || "—"}
                  </div>
                </div>
              </div>

              <div className="section">
                <h3>Auto-filed ticket</h3>
                <div className="ticket">🎫 {data.ticket_id || "—"}</div>
              </div>

              <div className="section">
                <h3>AI summary</h3>
                {!editing ? (
                  <div className="summary-box">
                    {data.edited_summary || data.summary || "—"}
                    {data.edited_summary && (
                      <div style={{ marginTop: 8, fontSize: 12, color: "#b7791f" }}>
                        (edited by {data.approved_by || "operator"})
                      </div>
                    )}
                  </div>
                ) : (
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                  />
                )}
                <div className="actions">
                  {!editing ? (
                    <>
                      <button
                        className="primary"
                        disabled={saving || data.approval_status === "approved"}
                        onClick={doApprove}
                      >
                        {data.approval_status === "approved"
                          ? "Approved ✓"
                          : "Approve"}
                      </button>
                      <button
                        className="secondary"
                        onClick={() => setEditing(true)}
                      >
                        Edit summary
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        className="primary"
                        disabled={saving}
                        onClick={doSaveEdit}
                      >
                        Save edit
                      </button>
                      <button
                        className="secondary"
                        onClick={() => {
                          setEditing(false);
                          setDraft(data.edited_summary || data.summary || "");
                        }}
                      >
                        Cancel
                      </button>
                    </>
                  )}
                </div>
              </div>

              <div className="section">
                <h3>Action items</h3>
                {data.action_items && data.action_items.length > 0 ? (
                  <ul className="action-items">
                    {data.action_items.map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                ) : (
                  <div style={{ color: "#64748b" }}>None</div>
                )}
              </div>

              <div className="section">
                <h3>
                  Full transcript{" "}
                  {data.stt_model && (
                    <span style={{ fontWeight: 400, textTransform: "none" }}>
                      · {data.stt_model}
                    </span>
                  )}
                </h3>
                <div className="transcript">
                  {data.transcript || "Transcript not available."}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

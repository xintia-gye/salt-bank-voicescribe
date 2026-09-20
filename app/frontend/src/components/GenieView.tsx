import { useEffect, useRef, useState } from "react";

interface GenieAnswer {
  conversation_id: string;
  message_id: string;
  status: string;
  text: string | null;
  sql: string | null;
  query_description: string | null;
  columns: string[];
  rows: string[][];
  suggested_questions: string[];
}

interface Turn {
  question: string;
  answer?: GenieAnswer;
  error?: string;
}

export default function GenieView() {
  const [samples, setSamples] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const convId = useRef<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/genie/info")
      .then((r) => r.json())
      .then((d) => setSamples(d.sample_questions || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, loading]);

  async function ask(question: string) {
    if (!question.trim() || loading) return;
    setInput("");
    setTurns((t) => [...t, { question }]);
    setLoading(true);
    try {
      const res = await fetch("/api/genie/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          conversation_id: convId.current,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const answer: GenieAnswer = await res.json();
      convId.current = answer.conversation_id;
      setTurns((t) => {
        const copy = [...t];
        copy[copy.length - 1] = { question, answer };
        return copy;
      });
    } catch (e) {
      setTurns((t) => {
        const copy = [...t];
        copy[copy.length - 1] = { question, error: String(e) };
        return copy;
      });
    } finally {
      setLoading(false);
    }
  }

  function resetConversation() {
    convId.current = null;
    setTurns([]);
  }

  return (
    <div className="container">
      <div className="genie-head">
        <div>
          <h2 className="genie-title">Ask Genie</h2>
          <p className="genie-sub">
            Natural-language analytics over the call-summary gold table
            (Databricks Genie). Ask a question in plain English.
          </p>
        </div>
        {turns.length > 0 && (
          <button className="secondary" onClick={resetConversation}>
            New conversation
          </button>
        )}
      </div>

      {turns.length === 0 && (
        <div className="genie-samples">
          {samples.map((q) => (
            <button key={q} className="chip-btn" onClick={() => ask(q)}>
              {q}
            </button>
          ))}
        </div>
      )}

      <div className="genie-thread">
        {turns.map((turn, i) => (
          <div key={i} className="genie-turn">
            <div className="genie-q">
              <span className="genie-avatar q">You</span>
              <div className="genie-bubble q">{turn.question}</div>
            </div>
            {turn.error && (
              <div className="genie-a">
                <span className="genie-avatar g">G</span>
                <div className="banner" style={{ margin: 0 }}>
                  {turn.error}
                </div>
              </div>
            )}
            {turn.answer && <GenieResult a={turn.answer} onAsk={ask} />}
          </div>
        ))}
        {loading && (
          <div className="genie-a">
            <span className="genie-avatar g">G</span>
            <div className="genie-bubble g typing">Genie is thinking…</div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="genie-input"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <input
          placeholder="Ask about categories, sentiment, agents, duration…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button className="primary" type="submit" disabled={loading || !input.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}

function GenieResult({
  a,
  onAsk,
}: {
  a: GenieAnswer;
  onAsk: (q: string) => void;
}) {
  const [showSql, setShowSql] = useState(false);
  return (
    <div className="genie-a">
      <span className="genie-avatar g">G</span>
      <div className="genie-bubble g">
        {a.text && <div className="genie-text">{a.text}</div>}

        {a.columns.length > 0 && (
          <div className="genie-table-wrap">
            <table>
              <thead>
                <tr>
                  {a.columns.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {a.rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {a.sql && (
          <div className="genie-sql-block">
            <button className="link-btn" onClick={() => setShowSql((s) => !s)}>
              {showSql ? "Hide SQL" : "Show generated SQL"}
            </button>
            {showSql && <pre className="genie-sql">{a.sql}</pre>}
          </div>
        )}

        {a.status !== "COMPLETED" && (
          <div className="genie-status">status: {a.status}</div>
        )}

        {a.suggested_questions.length > 0 && (
          <div className="genie-followups">
            {a.suggested_questions.map((q) => (
              <button key={q} className="chip-btn small" onClick={() => onAsk(q)}>
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

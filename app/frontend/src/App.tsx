import { useState } from "react";
import CallsView from "./components/CallsView";
import Dashboard from "./components/Dashboard";

type Tab = "calls" | "dashboard";

export default function App() {
  const [tab, setTab] = useState<Tab>("calls");

  return (
    <>
      <header className="header">
        <div className="brand">
          <div className="logo">S</div>
          <div>
            Salt Bank <span style={{ opacity: 0.9 }}>VoiceScribe</span>
            <br />
            <small>Call summarization · operator console</small>
          </div>
        </div>
        <nav className="tabs">
          <button
            className={`tab ${tab === "calls" ? "active" : ""}`}
            onClick={() => setTab("calls")}
          >
            Calls
          </button>
          <button
            className={`tab ${tab === "dashboard" ? "active" : ""}`}
            onClick={() => setTab("dashboard")}
          >
            Dashboard
          </button>
        </nav>
        <div className="spacer" />
        <div className="env">Internal tool · synthetic data</div>
      </header>

      {tab === "calls" ? <CallsView /> : <Dashboard />}
    </>
  );
}

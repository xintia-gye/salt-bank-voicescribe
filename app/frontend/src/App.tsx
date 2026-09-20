import { useState } from "react";
import CallsView from "./components/CallsView";
import Dashboard from "./components/Dashboard";
import GenieView from "./components/GenieView";

type Tab = "calls" | "dashboard" | "genie";

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
          <button
            className={`tab ${tab === "genie" ? "active" : ""}`}
            onClick={() => setTab("genie")}
          >
            Ask Genie
          </button>
        </nav>
        <div className="spacer" />
        <div className="env">Internal tool · synthetic data</div>
      </header>

      {tab === "calls" && <CallsView />}
      {tab === "dashboard" && <Dashboard />}
      {tab === "genie" && <GenieView />}
    </>
  );
}

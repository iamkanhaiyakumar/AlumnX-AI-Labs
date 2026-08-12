import React, { useState, useEffect, useRef } from "react";
import { API_BASE_URL, CANDIDATE_ID } from "./config";
import { generateSampleEmails } from "./services/sampleGenerator";

export default function App() {
  // Input State
  const [emailsInput, setEmailsInput] = useState("");
  const [parsedEmails, setParsedEmails] = useState([]);
  const [inputError, setInputError] = useState("");
  const [showAllRaw, setShowAllRaw] = useState(false);
  const [generateCount, setGenerateCount] = useState(250);

  // Ingestion & Results
  const [loadingIngest, setLoadingIngest] = useState(false);
  const [ingestResults, setIngestResults] = useState(null);

  // Database Ground-truth State
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState({
    processed: 0,
    created: 0,
    updated: 0,
    skipped: 0,
    duplicates: 0,
    spurious_count: 0,
    spurious_rate: 0,
    category_breakdown: {}
  });
  const [usersLookup, setUsersLookup] = useState({});

  // Chat State
  const [chatQuery, setChatQuery] = useState("");
  const [chatHistory, setChatHistory] = useState([
    {
      sender: "system",
      text: "Hello! I am your sales inbox routing assistant. Ask me questions about the processed emails, tasks, spurious rates, or runs.",
      timestamp: new Date().toLocaleTimeString()
    }
  ]);
  const [loadingChat, setLoadingChat] = useState(false);
  const chatEndRef = useRef(null);

  // Load initial configurations, seed users and cache statistics
  useEffect(() => {
    fetchUsers();
    refreshDashboard();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const refreshDashboard = () => {
    fetchTasks();
    fetchStats();
  };

  const fetchUsers = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/users`);
      if (res.ok) {
        const users = await res.json();
        const lookup = {};
        users.forEach(u => {
          lookup[u.user_id] = u.name;
        });
        setUsersLookup(lookup);
      }
    } catch (e) {
      console.error("Failed to fetch users: ", e);
    }
  };

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/tasks?candidate_id=${CANDIDATE_ID}`);
      if (res.ok) {
        const data = await res.json();
        setTasks(data);
      }
    } catch (e) {
      console.error("Failed to fetch tasks: ", e);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/stats?candidate_id=${CANDIDATE_ID}`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.error("Failed to fetch stats: ", e);
    }
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    setEmailsInput(val);
    if (!val.trim()) {
      setParsedEmails([]);
      setInputError("");
      return;
    }
    
    try {
      const parsed = JSON.parse(val);
      if (Array.isArray(parsed)) {
        setParsedEmails(parsed);
        setInputError("");
      } else if (parsed.emails && Array.isArray(parsed.emails)) {
        setParsedEmails(parsed.emails);
        setInputError("");
      } else {
        setParsedEmails([]);
        setInputError("JSON must be an array of email objects or contain an 'emails' key.");
      }
    } catch (err) {
      setParsedEmails([]);
      setInputError("Invalid JSON format.");
    }
  };

  const handleGenerateSample = () => {
    const samples = generateSampleEmails(generateCount);
    const formatted = JSON.stringify(samples, null, 2);
    setEmailsInput(formatted);
    setParsedEmails(samples);
    setInputError("");
  };

  const handleProcessBatch = async () => {
    if (parsedEmails.length === 0) return;
    setLoadingIngest(true);
    setIngestResults(null);

    const BATCH_SIZE = 100;
    let totalProcessed = 0;
    let totalCreated = 0;
    let totalUpdated = 0;
    let totalSkipped = 0;
    let allErrors = [];

    try {
      // Chunk parsedEmails array into batches of 100 to respect backend limit
      for (let i = 0; i < parsedEmails.length; i += BATCH_SIZE) {
        const chunk = parsedEmails.slice(i, i + BATCH_SIZE);
        const res = await fetch(`${API_BASE_URL}/ingest`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            candidate_id: CANDIDATE_ID,
            emails: chunk
          })
        });

        if (res.ok) {
          const data = await res.json();
          totalProcessed += data.processed;
          totalCreated += data.tasks_created;
          totalUpdated += data.tasks_updated;
          totalSkipped += data.skipped;
          if (data.errors) {
            allErrors = allErrors.concat(data.errors);
          }
        } else {
          const errData = await res.json();
          alert(`Ingestion failed at batch ${Math.floor(i / BATCH_SIZE) + 1}: ${errData.detail || "Unknown error"}`);
          break;
        }
      }

      setIngestResults({
        processed: totalProcessed,
        tasks_created: totalCreated,
        tasks_updated: totalUpdated,
        skipped: totalSkipped,
        errors: allErrors
      });
      refreshDashboard();
    } catch (e) {
      alert(`Network error running ingestion: ${e.message}`);
    } finally {
      setLoadingIngest(false);
    }
  };

  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!chatQuery.trim()) return;

    const userMsg = {
      sender: "user",
      text: chatQuery,
      timestamp: new Date().toLocaleTimeString()
    };
    setChatHistory(prev => [...prev, userMsg]);
    setLoadingChat(true);
    const queryToSend = chatQuery;
    setChatQuery("");

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_id: CANDIDATE_ID,
          query: queryToSend
        })
      });

      if (res.ok) {
        const data = await res.json();
        setChatHistory(prev => [...prev, {
          sender: "system",
          text: data.answer,
          data: data.supporting_data,
          timestamp: new Date().toLocaleTimeString()
        }]);
      } else {
        setChatHistory(prev => [...prev, {
          sender: "system",
          text: "Sorry, I had trouble connecting to the chat engine.",
          timestamp: new Date().toLocaleTimeString()
        }]);
      }
    } catch (err) {
      setChatHistory(prev => [...prev, {
        sender: "system",
        text: `Network error: ${err.message}`,
        timestamp: new Date().toLocaleTimeString()
      }]);
    } finally {
      setLoadingChat(false);
    }
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div>
          <h1>Sales Inbox → Task Router</h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.2rem" }}>
            Autonomous Ingestion, Hybrid Intent Classification & Grounded Analytics
          </p>
        </div>
        <div className="header-status">
          <span className="candidate-badge">Candidate ID: {CANDIDATE_ID}</span>
          <div className="status-indicator">
            <span className="status-dot"></span>
            <span>Active</span>
          </div>
        </div>
      </header>

      {/* Main Ingestion Panel */}
      <section className="ingest-card">
        <h2 className="card-title">
          📥 Email Batch Ingestion
        </h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Paste a JSON array of emails (up to 100) or generate 250 sample emails to see the system process them.
        </p>
        
        <div className="textarea-container">
          <textarea
            className="json-textarea"
            placeholder="[ { 'email_id': 'em_01', 'thread_id': 'th_01', ... } ]"
            value={emailsInput}
            onChange={handleInputChange}
          />
        </div>

        {inputError && (
          <p style={{ color: "var(--status-error)", fontSize: "0.85rem" }}>{inputError}</p>
        )}

        <div className="btn-group">
          <button
            className="btn btn-primary"
            onClick={handleProcessBatch}
            disabled={loadingIngest || parsedEmails.length === 0}
          >
            {loadingIngest ? (
              <>
                <div className="spinner"></div>
                <span>Processing...</span>
              </>
            ) : (
              <span>Process Batch ({parsedEmails.length} emails)</span>
            )}
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontSize: "0.9rem", color: "var(--text-secondary)" }}>Count:</span>
            <input 
              type="number" 
              min="1" 
              max="250"
              style={{
                width: "75px",
                background: "rgba(8, 7, 16, 0.6)",
                border: "1px solid var(--border-muted)",
                borderRadius: "8px",
                padding: "0.5rem",
                color: "white",
                outline: "none",
                fontSize: "0.9rem",
                textAlign: "center"
              }}
              value={generateCount}
              onChange={(e) => setGenerateCount(Math.max(1, Math.min(250, Number(e.target.value))))}
              disabled={loadingIngest}
            />
            <button className="btn btn-secondary" onClick={handleGenerateSample} disabled={loadingIngest}>
              🔄 Generate Sample Emails
            </button>
          </div>
        </div>
      </section>

      {/* Raw Email Table (Rendered immediately BEFORE routing) */}
      {parsedEmails.length > 0 && (
        <section className="table-card">
          <h2 className="card-title">Raw Input Emails ({parsedEmails.length} loaded)</h2>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>From</th>
                  <th>Subject</th>
                  <th>Received At</th>
                  <th>Thread ID</th>
                  <th>Body Preview</th>
                </tr>
              </thead>
              <tbody>
                {parsedEmails.slice(0, showAllRaw ? parsedEmails.length : 5).map((email, idx) => (
                  <tr key={email.email_id || idx}>
                    <td>
                      <div>{email.from_name || "—"}</div>
                      <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>{email.from_email}</div>
                    </td>
                    <td>{email.subject}</td>
                    <td>{new Date(email.received_at).toLocaleString()}</td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>{email.thread_id}</td>
                    <td className="text-truncate">{email.body}</td>
                  </tr>
                ))}
                {parsedEmails.length > 5 && (
                  <tr 
                    style={{ cursor: "pointer", backgroundColor: "rgba(255, 255, 255, 0.02)" }}
                    onClick={() => setShowAllRaw(!showAllRaw)}
                  >
                    <td colSpan="5" style={{ textAlign: "center", color: "var(--accent-cyan)", fontWeight: 600 }}>
                      {showAllRaw 
                        ? "▲ Click to collapse raw email table" 
                        : `▼ ... and ${parsedEmails.length - 5} more emails in the loaded batch. Click to expand.`}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Ingest Result Banner */}
      {ingestResults && (
        <section className="stat-item" style={{ borderColor: "var(--accent-purple)", background: "rgba(147, 51, 234, 0.05)" }}>
          <h3 className="card-title" style={{ color: "#c084fc" }}>Ingestion Summary</h3>
          <div className="stats-grid" style={{ marginTop: "0.8rem" }}>
            <div>
              <div className="stat-label">Processed</div>
              <div className="stat-value">{ingestResults.processed}</div>
            </div>
            <div>
              <div className="stat-label">Tasks Created</div>
              <div className="stat-value" style={{ color: "var(--status-created)" }}>{ingestResults.tasks_created}</div>
            </div>
            <div>
              <div className="stat-label">Tasks Updated</div>
              <div className="stat-value" style={{ color: "var(--status-updated)" }}>{ingestResults.tasks_updated}</div>
            </div>
            <div>
              <div className="stat-label">Emails Skipped</div>
              <div className="stat-value" style={{ color: "var(--status-skipped)" }}>{ingestResults.skipped}</div>
            </div>
          </div>
        </section>
      )}

      {/* Database Statistics */}
      <section className="table-card">
        <h2 className="card-title">📊 Database Totals & Performance</h2>
        <div className="stats-grid">
          <div className="stat-item">
            <span className="stat-label">Total Processed</span>
            <span className="stat-value">{stats.processed}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Tasks Created</span>
            <span className="stat-value" style={{ color: "var(--status-created)" }}>{stats.created}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Tasks Updated</span>
            <span className="stat-value" style={{ color: "var(--status-updated)" }}>{stats.updated}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Emails Skipped</span>
            <span className="stat-value" style={{ color: "var(--status-skipped)" }}>{stats.skipped}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Spurious Skips</span>
            <span className="stat-value" style={{ color: "var(--priority-high)" }}>{stats.spurious_count}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Spurious Rate</span>
            <span className="stat-value" style={{ color: "#f87171" }}>{(stats.spurious_rate * 100).toFixed(1)}%</span>
          </div>
        </div>
      </section>

      {/* Main Grid: Routed Tasks List + Grounded Chat Panel */}
      <div className="dashboard-grid">
        {/* Routed Tasks Table */}
        <section className="table-card" style={{ height: "600px", display: "flex", flexDirection: "column" }}>
          <h2 className="card-title">📋 Routed Tasks ({tasks.length})</h2>
          <div className="table-wrapper" style={{ flex: 1, overflowY: "auto" }}>
            <table className="data-table">
              <thead style={{ position: "sticky", top: 0, zIndex: 1 }}>
                <tr>
                  <th>Task Title</th>
                  <th>From</th>
                  <th>Assignee</th>
                  <th>Category</th>
                  <th>Priority</th>
                  <th>Due Date</th>
                  <th>Deal Value</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {tasks.length === 0 ? (
                  <tr>
                    <td colSpan="8" style={{ textAlign: "center", padding: "3rem", color: "var(--text-secondary)" }}>
                      No tasks processed yet. Paste an email batch above to begin.
                    </td>
                  </tr>
                ) : (
                  tasks.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{item.task?.title || "—"}</div>
                        <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                          {item.task?.company_name || "Unknown Company"}
                        </div>
                      </td>
                      <td>
                        <div style={{ fontWeight: 500 }}>{item.email?.from_name || "—"}</div>
                        <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                          {item.email?.from_email || "—"}
                        </div>
                      </td>
                      <td>
                        <span className="badge" style={{ background: "rgba(168, 85, 247, 0.15)", color: "#d8b4fe" }}>
                           {usersLookup[item.task?.assignee_id] || item.task?.assignee_id || (item.decision === "skipped" ? "—" : "Triage")}
                        </span>
                      </td>
                      <td>{item.task?.category}</td>
                      <td>
                        <span className={`priority-${item.task?.priority}`}>
                          {item.task?.priority}
                        </span>
                      </td>
                      <td>{item.task?.due_date || "—"}</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>
                        {item.task?.deal_value_inr ? `₹${item.task.deal_value_inr.toLocaleString()}` : "—"}
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                          <div style={{ width: "40px", background: "rgba(255,255,255,0.05)", height: "6px", borderRadius: "3px" }}>
                            <div style={{ width: `${(item.task?.confidence || 0) * 100}%`, background: "var(--accent-cyan)", height: "100%", borderRadius: "3px" }}></div>
                          </div>
                          <span>{item.task?.confidence}</span>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Conversational Grounded Chat */}
        <section className="chat-card">
          <h2 className="card-title">💬 Grounded Analytics Chat</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginBottom: "0.8rem" }}>
            Ask questions grounded strictly in database records. Hallucinations are actively blocked.
          </p>

          <div className="chat-history">
            {chatHistory.map((msg, index) => (
              <div key={index} className={`chat-message ${msg.sender}`}>
                <div>{msg.text}</div>
                {msg.data && (
                  <details className="supporting-data-box">
                    <summary style={{ cursor: "pointer", outline: "none", userSelect: "none" }}>supporting_data</summary>
                    <pre style={{ marginTop: "0.4rem", whiteSpace: "pre-wrap" }}>
                      {JSON.stringify(msg.data, null, 2)}
                    </pre>
                  </details>
                )}
                <span className="chat-time">{msg.timestamp}</span>
              </div>
            ))}
            {loadingChat && (
              <div className="chat-message system">
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <div className="spinner"></div>
                  <span>Grounded query planning...</span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <form onSubmit={handleSendChat} className="chat-input-area">
            <input
              type="text"
              className="chat-input"
              placeholder="Ask stats, counts, rates or list tasks..."
              value={chatQuery}
              onChange={(e) => setChatQuery(e.target.value)}
              disabled={loadingChat}
            />
            <button className="btn btn-primary" type="submit" disabled={loadingChat || !chatQuery.trim()}>
              Send
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}

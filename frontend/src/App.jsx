import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { getPredictions, getOpportunityAlerts, runLiveAgent } from "./services/api";
import MarketRegime from "./components/MarketRegime";

function App() {
  const [predictions, setPredictions] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [cycle, setCycle] = useState(null);
  const [darkMode, setDarkMode] = useState(true);

  async function loadDashboard() {
    try {
      setLoading(true);
      setError("");
      const [predictionData, alertData] = await Promise.all([
        getPredictions(),
        getOpportunityAlerts(20),
      ]);
      setPredictions(Array.isArray(predictionData) ? predictionData : []);
      setAlerts(Array.isArray(alertData) ? alertData : []);
    } catch (err) {
      console.error(err);
      setError("Unable to connect to the backend API.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
    const timer = setInterval(loadDashboard, 60_000);
    return () => clearInterval(timer);
  }, []);

  async function runAgentNow() {
    try {
      setRunning(true);
      setError("");
      const result = await runLiveAgent();
      setCycle(result);
      await loadDashboard();
    } catch (err) {
      console.error(err);
      setError("Live intelligence cycle failed. Check the backend console.");
    } finally {
      setRunning(false);
    }
  }

  const stats = useMemo(() => ({
    total: predictions.length,
    buy: predictions.filter((p) => String(p.signal).toUpperCase() === "BUY").length,
    alerts: alerts.length,
    highConfidence: alerts.filter((a) => Number(a.confidence) >= 0.7).length,
  }), [predictions, alerts]);

  const topOpportunities = useMemo(() => [...alerts]
    .sort((a, b) => Number(b.opportunity_score || 0) - Number(a.opportunity_score || 0))
    .slice(0, 6), [alerts]);

  const formatPercent = (value) => {
    const n = Number(value);
    return Number.isFinite(n) ? `${n >= 0 ? "+" : ""}${n.toFixed(2)}%` : "—";
  };

  const formatConfidence = (value) => {
    const n = Number(value);
    return Number.isFinite(n) ? `${(n * 100).toFixed(0)}%` : "—";
  };

  const signalClass = (signal) => {
    const value = String(signal || "").toLowerCase();
    if (value === "buy") return "signal-buy";
    if (value === "sell" || value === "avoid") return "signal-sell";
    return "signal-hold";
  };

  return (
    <div className={darkMode ? "app dark" : "app light"}>
      <header className="dashboard-header">
        <div>
          <h1>Stock Agent</h1>
          <p>Real-time market intelligence → early opportunity detection</p>
        </div>
        <div className="header-actions">
          <button className="refresh-button" onClick={runAgentNow} disabled={running}>
            {running ? "Scanning..." : "⚡ Scan Internet Now"}
          </button>
          <button className="refresh-button" onClick={loadDashboard} disabled={loading}>Refresh</button>
          <button className="theme-button" onClick={() => setDarkMode((v) => !v)}>{darkMode ? "☀ Light" : "☾ Dark"}</button>
        </div>
      </header>

      <main className="dashboard-content">
        {error && <div className="error-banner">{error}</div>}

        <section className="section" style={{ border: "1px solid rgba(34,197,94,.35)" }}>
          <div className="section-header">
            <div>
              <h2>🚨 Live Opportunities</h2>
              <p>Real-world events detected from the agent's news intelligence pipeline. These are opportunities, not generic ML predictions.</p>
            </div>
            <span className="signal signal-buy">LIVE · 5 MIN CYCLE</span>
          </div>

          {topOpportunities.length === 0 ? (
            <div className="empty-state">
              <strong>No actionable opportunity detected yet.</strong>
              <p style={{ marginTop: 8 }}>Click <b>Scan Internet Now</b>. The agent will collect current news, interpret the event, map affected companies, check market reaction and create an alert when the evidence is strong enough.</p>
            </div>
          ) : (
            <div className="opportunity-grid">
              {topOpportunities.map((alert) => (
                <article className="opportunity-card" key={alert.id}>
                  <div className="opportunity-top">
                    <div>
                      <h3>{alert.symbol}</h3>
                      <span className={`signal ${signalClass(alert.action)}`}>{alert.action}</span>
                    </div>
                    <strong>{Number(alert.opportunity_score).toFixed(0)}/100</strong>
                  </div>
                  <p style={{ margin: "14px 0 8px", fontWeight: 700 }}>{alert.title}</p>
                  <p style={{ margin: 0, lineHeight: 1.6 }}>{alert.reason}</p>
                  <div className="opportunity-details" style={{ marginTop: 16 }}>
                    <div><span>Confidence</span><strong>{formatConfidence(alert.confidence)}</strong></div>
                    <div><span>Risk</span><strong>{alert.risk || "—"}</strong></div>
                    <div><span>Horizon</span><strong>{alert.expected_horizon || "—"}</strong></div>
                  </div>
                  {alert.source_url && <div style={{ marginTop: 14 }}><a href={alert.source_url} target="_blank" rel="noreferrer">Read source evidence →</a></div>}
                </article>
              ))}
            </div>
          )}
        </section>

        {cycle && (
          <section className="section">
            <div className="section-header"><div><h2>Latest Intelligence Cycle</h2><p>What the agent just processed</p></div></div>
            <div className="stats-grid">
              <div className="stat-card"><span>Articles collected</span><strong>{cycle.collected ?? 0}</strong></div>
              <div className="stat-card"><span>New articles</span><strong>{cycle.inserted ?? 0}</strong></div>
              <div className="stat-card"><span>Articles processed</span><strong>{cycle.opportunities?.articles_processed ?? 0}</strong></div>
              <div className="stat-card buy-card"><span>Alerts created</span><strong>{cycle.opportunities?.alerts_created ?? 0}</strong></div>
            </div>
          </section>
        )}

        <MarketRegime />

        <section className="stats-grid">
          <div className="stat-card"><span>ML Predictions</span><strong>{stats.total}</strong></div>
          <div className="stat-card buy-card"><span>BUY Signals</span><strong>{stats.buy}</strong></div>
          <div className="stat-card"><span>Live Alerts</span><strong>{stats.alerts}</strong></div>
          <div className="stat-card"><span>High Confidence</span><strong>{stats.highConfidence}</strong></div>
        </section>

        <section className="section">
          <div className="section-header"><div><h2>Model Predictions</h2><p>Secondary quantitative forecasts</p></div></div>
          <div className="table-container">
            {loading ? <div className="empty-state">Loading...</div> : predictions.length === 0 ? <div className="empty-state">No model predictions available.</div> : (
              <table>
                <thead><tr><th>Stock</th><th>Signal</th><th>5D</th><th>10D</th><th>20D</th><th>Confidence</th><th>Price</th><th>Model</th></tr></thead>
                <tbody>{predictions.map((p) => (
                  <tr key={p.id}>
                    <td className="stock-name">{p.symbol}</td>
                    <td><span className={`signal ${signalClass(p.signal)}`}>{p.signal || "HOLD"}</span></td>
                    <td className={Number(p.predicted_return_5d) >= 0 ? "positive" : "negative"}>{formatPercent(p.predicted_return_5d)}</td>
                    <td>{formatPercent(p.predicted_return_10d)}</td>
                    <td>{formatPercent(p.predicted_return_20d)}</td>
                    <td>{formatConfidence(p.confidence)}</td>
                    <td>{Number.isFinite(Number(p.price_at_prediction)) ? Number(p.price_at_prediction).toFixed(2) : "—"}</td>
                    <td>{p.model_name || "—"}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;

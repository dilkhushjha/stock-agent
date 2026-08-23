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
  const [darkMode, setDarkMode] = useState(false);

  async function loadDashboard() {
    try {
      setLoading(true); setError("");
      const [predictionData, alertData] = await Promise.all([getPredictions(), getOpportunityAlerts(20)]);
      setPredictions(Array.isArray(predictionData) ? predictionData : []);
      setAlerts(Array.isArray(alertData) ? alertData : []);
    } catch (err) { console.error(err); setError("Unable to connect to the backend API."); }
    finally { setLoading(false); }
  }

  useEffect(() => { loadDashboard(); const timer = setInterval(loadDashboard, 60_000); return () => clearInterval(timer); }, []);

  async function runAgentNow() {
    try { setRunning(true); setError(""); setCycle(await runLiveAgent()); await loadDashboard(); }
    catch (err) { console.error(err); setError("Live intelligence scan failed. Check the backend console."); }
    finally { setRunning(false); }
  }

  const stats = useMemo(() => ({
    total: predictions.length,
    buy: predictions.filter((p) => String(p.signal).toUpperCase() === "BUY").length,
    alerts: alerts.length,
    highConfidence: alerts.filter((a) => Number(a.confidence) >= 0.7).length,
  }), [predictions, alerts]);
  const topOpportunities = useMemo(() => [...alerts].sort((a,b) => Number(b.opportunity_score||0)-Number(a.opportunity_score||0)).slice(0,6), [alerts]);
  const formatPercent = (v) => Number.isFinite(Number(v)) ? `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(2)}%` : "—";
  const formatConfidence = (v) => Number.isFinite(Number(v)) ? `${(Number(v)*100).toFixed(0)}%` : "—";
  const signalClass = (v) => ["buy"].includes(String(v||"").toLowerCase()) ? "signal-buy" : ["sell","avoid"].includes(String(v||"").toLowerCase()) ? "signal-sell" : "signal-hold";

  return <div className={darkMode ? "app dark" : "app light"}>
    <header className="dashboard-header">
      <div className="brand"><div className="brand-mark">S</div><div><h1>StockAgent</h1><p>Real-time market intelligence · early opportunity detection</p></div></div>
      <div className="header-actions">
        <button className="primary-button" onClick={runAgentNow} disabled={running}>{running ? "Scanning…" : "⚡ Scan now"}</button>
        <button className="icon-button" onClick={loadDashboard} disabled={loading} title="Refresh">↻</button>
        <button className="theme-button" onClick={() => setDarkMode(v=>!v)} title="Toggle theme">{darkMode ? "☀" : "☾"}</button>
      </div>
    </header>

    <main className="dashboard-content">
      {error && <div className="error-banner">{error}</div>}
      <section className="hero-panel">
        <div><div className="eyebrow"><span className="live-dot"/> LIVE INTELLIGENCE</div><h2>What is happening in the market <span>right now?</span></h2><p>StockAgent connects real-world events, company exposure and market behaviour to surface opportunities before they become obvious.</p></div>
        <div className="hero-metric"><strong>{topOpportunities.length}</strong><span>actionable alerts</span></div>
      </section>

      <section className="section opportunity-section">
        <div className="section-header"><div><h2>🚨 Live Opportunities</h2><p>Potential market-moving situations that currently deserve attention.</p></div><span className="status-pill"><i/> LIVE · 5 MIN</span></div>
        {topOpportunities.length === 0 ? <div className="empty-opportunity"><div className="empty-icon">⌁</div><div><strong>No actionable opportunity detected</strong><p>Run a scan to analyze the latest news and market conditions.</p></div><button className="secondary-button" onClick={runAgentNow} disabled={running}>{running ? "Scanning…" : "Run scan"}</button></div> : <div className="opportunity-grid">
          {topOpportunities.map((a,i)=><article className={`opportunity-card ${i===0?"featured":""}`} key={a.id}>
            <div className="opportunity-top"><div><span className={`signal ${signalClass(a.action)}`}>{a.action||"WATCH"}</span><h3>{a.symbol}</h3></div><div className="score"><strong>{Number(a.opportunity_score||0).toFixed(0)}</strong><span>/100</span></div></div>
            <p className="opportunity-title">{a.title}</p><p className="opportunity-reason">{a.reason}</p>
            <div className="opportunity-details"><div><span>Confidence</span><strong>{formatConfidence(a.confidence)}</strong></div><div><span>Risk</span><strong>{a.risk||"—"}</strong></div><div><span>Horizon</span><strong>{a.expected_horizon||"—"}</strong></div></div>
            {a.source_url && <a className="source-link" href={a.source_url} target="_blank" rel="noreferrer">View evidence →</a>}
          </article>)}
        </div>}
      </section>

      {cycle && <section className="section"><div className="section-header"><div><h2>Latest scan</h2><p>Results from the most recent intelligence cycle.</p></div></div><div className="stats-grid cycle-stats"><div className="stat-card"><span>Articles collected</span><strong>{cycle.collected??0}</strong></div><div className="stat-card"><span>New articles</span><strong>{cycle.inserted??0}</strong></div><div className="stat-card"><span>Articles processed</span><strong>{cycle.opportunities?.articles_processed??0}</strong></div><div className="stat-card buy-card"><span>Alerts created</span><strong>{cycle.opportunities?.alerts_created??0}</strong></div></div></section>}

      <section className="section"><MarketRegime/></section>
      <section className="stats-grid summary-stats"><div className="stat-card"><span>Model predictions</span><strong>{stats.total}</strong></div><div className="stat-card buy-card"><span>BUY signals</span><strong>{stats.buy}</strong></div><div className="stat-card"><span>Live alerts</span><strong>{stats.alerts}</strong></div><div className="stat-card"><span>High confidence</span><strong>{stats.highConfidence}</strong></div></section>
      <section className="section"><div className="section-header"><div><h2>Model predictions</h2><p>Quantitative forecasts are supporting evidence, not the primary alert engine.</p></div></div><div className="table-container">{loading?<div className="empty-state">Loading predictions…</div>:predictions.length===0?<div className="empty-state">No model predictions available.</div>:<table><thead><tr><th>Stock</th><th>Signal</th><th>5D</th><th>10D</th><th>20D</th><th>Confidence</th><th>Price</th><th>Model</th></tr></thead><tbody>{predictions.map(p=><tr key={p.id}><td className="stock-name">{p.symbol}</td><td><span className={`signal ${signalClass(p.signal)}`}>{p.signal||"HOLD"}</span></td><td className={Number(p.predicted_return_5d)>=0?"positive":"negative"}>{formatPercent(p.predicted_return_5d)}</td><td>{formatPercent(p.predicted_return_10d)}</td><td>{formatPercent(p.predicted_return_20d)}</td><td>{formatConfidence(p.confidence)}</td><td>{Number.isFinite(Number(p.price_at_prediction))?Number(p.price_at_prediction).toFixed(2):"—"}</td><td>{p.model_name||"—"}</td></tr>)}</tbody></table>}</div></section>
    </main>
  </div>;
}
export default App;

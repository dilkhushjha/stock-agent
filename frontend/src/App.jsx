import { useEffect, useState } from "react";
import "./App.css";
import { getRecommendations, runLiveAgent } from "./services/api";

const pct = (v) => Number.isFinite(Number(v)) ? `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(2)}%` : "—";
const money = (v) => Number.isFinite(Number(v)) ? `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "—";
const percent = (v) => Number.isFinite(Number(v)) ? `${(Number(v) * 100).toFixed(0)}%` : "—";
const metric = (v, suffix = "") => Number.isFinite(Number(v)) ? `${Number(v).toFixed(2)}${suffix}` : "—";

function Fundamental({ label, value }) {
  return <div className="fundamental"><span>{label}</span><strong>{value}</strong></div>;
}

function RecommendationCard({ item }) {
  const f = item.fundamentals || {};
  return <article className="recommendation-card">
    <div className="rec-head">
      <div className="rank">#{item.rank}</div>
      <div className="identity"><div className="symbol-row"><h2>{item.symbol}</h2><span className={`action ${item.action === "BUY" ? "buy" : "watch"}`}>{item.action}</span></div><p>{item.company}{item.sector ? ` · ${item.sector}` : ""}</p></div>
      <div className="score"><strong>{item.score.toFixed(0)}</strong><span>/100</span><small>conviction</small></div>
    </div>

    <div className="thesis"><span>WHY THIS STOCK</span><h3>{item.thesis}</h3><p>{item.reason}</p></div>

    <div className="evidence-row"><div><span>Why now</span><strong>{item.why_now}</strong></div><div><span>Risk</span><strong>{item.risk}</strong></div><div><span>Horizon</span><strong>{item.horizon || "—"}</strong></div><div><span>Confidence</span><strong>{percent(item.confidence)}</strong></div></div>

    <div className="analysis-grid">
      <section><h4>Fundamentals</h4><div className="fundamental-grid"><Fundamental label="P/E" value={metric(f.pe)} /><Fundamental label="ROE" value={percent(f.roe)} /><Fundamental label="Debt / Equity" value={metric(f.debt_to_equity)} /><Fundamental label="Profit margin" value={percent(f.profit_margin)} /><Fundamental label="Revenue growth" value={percent(f.revenue_growth)} /><Fundamental label="Earnings growth" value={percent(f.earnings_growth)} /></div></section>
      <section><h4>Prediction</h4><div className="prediction-box"><div><span>5D expected</span><strong className={Number(item.predicted_5d) >= 0 ? "positive" : "negative"}>{pct(item.predicted_5d)}</strong></div><div><span>20D expected</span><strong className={Number(item.predicted_20d) >= 0 ? "positive" : "negative"}>{pct(item.predicted_20d)}</strong></div><div><span>Model signal</span><strong>{item.model_signal || "—"}</strong></div><div><span>Model evidence</span><strong>{item.model_score.toFixed(0)}/100</strong></div></div></section>
    </div>

    <div className="entry-strip"><div><span>Current price</span><strong>{money(item.current_price)}</strong></div><div><span>Preferred accumulation</span><strong>{item.entry_low && item.entry_high ? `${money(item.entry_low)} – ${money(item.entry_high)}` : "Refresh market data"}</strong></div><div className="invalidation"><span>Thesis invalidation</span><strong>{item.invalidation}</strong></div></div>

    {item.evidence?.source_url && <div className="card-footer"><span>Evidence: {item.evidence.source || "market source"}</span><a href={item.evidence.source_url} target="_blank" rel="noreferrer">Read source →</a></div>}
  </article>;
}

function App() {
  const [recommendations, setRecommendations] = useState([]);
  const [generatedAt, setGeneratedAt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      setError("");
      const data = await getRecommendations(5);
      setRecommendations(data.recommendations || []);
      setGeneratedAt(data.generated_at);
    } catch (e) {
      console.error(e);
      setError("StockAgent could not load its recommendations. Make sure the backend is running.");
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); const timer = setInterval(load, 60_000); return () => clearInterval(timer); }, []);

  async function scan() {
    try { setRunning(true); setError(""); await runLiveAgent(); await load(); }
    catch (e) { console.error(e); setError("Live intelligence scan failed. Check the backend console."); }
    finally { setRunning(false); }
  }

  return <div className="app">
    <header><div className="brand"><div className="logo">S</div><div><h1>StockAgent</h1><p>AI-powered Indian stock intelligence</p></div></div><button className="scan" onClick={scan} disabled={running}>{running ? "Analyzing…" : "↻ Analyze now"}</button></header>
    <main>
      <section className="intro"><div><div className="live"><i/> LIVE INTELLIGENCE</div><h2>Stocks worth considering <span>right now.</span></h2><p>StockAgent filters the market and gives you a small shortlist backed by current events, news, company fundamentals, historical evidence, market behaviour and quantitative prediction.</p></div><div className="updated">{generatedAt ? `Updated ${new Date(generatedAt).toLocaleTimeString()}` : "Analyzing market…"}</div></section>
      {error && <div className="error">{error}</div>}
      {loading ? <div className="empty">Analyzing current opportunities…</div> : recommendations.length === 0 ? <div className="empty"><strong>No high-conviction recommendation yet.</strong><p>StockAgent will keep monitoring events and market conditions. Run an analysis to refresh the thesis.</p><button className="secondary" onClick={scan} disabled={running}>{running ? "Analyzing…" : "Analyze now"}</button></div> : <section className="recommendations"><div className="section-title"><div><h3>Top recommendations</h3><p>Maximum 5 ideas. The system deliberately avoids turning this into a broker terminal.</p></div><span>{recommendations.length} ideas</span></div>{recommendations.map((item) => <RecommendationCard key={`${item.symbol}-${item.rank}`} item={item} />)}</section>}
      <section className="method"><h3>How StockAgent reaches a recommendation</h3><div className="method-flow"><span>News & events</span><b>→</b><span>Economic impact</span><b>→</b><span>Company exposure</span><b>→</b><span>Fundamentals</span><b>→</b><span>ML prediction</span><b>→</b><strong>Recommendation</strong></div></section>
    </main>
  </div>;
}

export default App;

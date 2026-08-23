import { useEffect, useState } from "react";
import "./App.css";
import { getIntelligenceOverview, getRecommendations, runLiveAgent } from "./services/api";

const pct = (v) => Number.isFinite(Number(v)) ? `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(2)}%` : "—";
const money = (v) => Number.isFinite(Number(v)) ? `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "—";
const percent = (v) => Number.isFinite(Number(v)) ? `${(Number(v) * 100).toFixed(0)}%` : "—";
const metric = (v, suffix = "") => Number.isFinite(Number(v)) ? `${Number(v).toFixed(2)}${suffix}` : "—";
const label = (v) => String(v || "MARKET").replaceAll("_", " ");

function Fundamental({ label: name, value }) {
  return <div className="fundamental"><span>{name}</span><strong>{value}</strong></div>;
}

function NewsCard({ item }) {
  return <article className="news-card">
    <div className="news-meta"><span className="news-category">{label(item.category)}</span><span>{item.source || "News source"}</span><span>{item.published_at ? new Date(item.published_at).toLocaleString() : ""}</span></div>
    <h3>{item.title}</h3>
    <p className="news-summary">{item.summary || "No summary available."}</p>
    <div className="impact-grid">
      <div><span>Potential sector impact</span><strong>{item.sector || "Under analysis"}</strong></div>
      <div><span>Direction</span><strong>{label(item.direction) || "—"}</strong></div>
      <div><span>Impact</span><strong>{label(item.impact) || "—"}</strong></div>
      <div><span>Time horizon</span><strong>{item.horizon || "—"}</strong></div>
    </div>
    <div className="real-world"><span>REAL-WORLD EFFECT</span><p>{item.real_world_effect}</p></div>
    {item.source_url && <a className="source-link" href={item.source_url} target="_blank" rel="noreferrer">Read original news →</a>}
  </article>;
}

function RecommendationCard({ item }) {
  const f = item.fundamentals || {};
  const news = item.news || {};
  const event = item.event || {};
  return <article className="recommendation-card">
    <div className="rec-head">
      <div className="rank">#{item.rank}</div>
      <div className="identity"><div className="symbol-row"><h2>{item.symbol}</h2><span className={`action ${item.action === "BUY" ? "buy" : "watch"}`}>{item.action}</span></div><p>{item.company}{item.sector ? ` · ${item.sector}` : ""}</p></div>
      <div className="score"><strong>{Number(item.score || 0).toFixed(0)}</strong><span>/100</span><small>conviction</small></div>
    </div>

    <div className="thesis"><span>THE INVESTMENT THESIS</span><h3>{item.thesis}</h3><p>{item.reason}</p></div>

    <div className="catalyst"><div><span>CATALYST / NEWS</span><strong>{news.title || event.title || "Current market event"}</strong><small>{news.source || "Internal intelligence"}</small></div><div><span>REAL-WORLD IMPACT</span><p>{event.description || item.why_now}</p></div></div>

    <div className="evidence-row"><div><span>Why now</span><strong>{item.why_now}</strong></div><div><span>Risk</span><strong>{item.risk}</strong></div><div><span>Horizon</span><strong>{item.horizon || "—"}</strong></div><div><span>Confidence</span><strong>{percent(item.confidence)}</strong></div></div>

    <div className="analysis-grid">
      <section><h4>Company fundamentals</h4><div className="fundamental-grid"><Fundamental label="P/E" value={metric(f.pe)} /><Fundamental label="ROE" value={percent(f.roe)} /><Fundamental label="Debt / Equity" value={metric(f.debt_to_equity)} /><Fundamental label="Profit margin" value={percent(f.profit_margin)} /><Fundamental label="Revenue growth" value={percent(f.revenue_growth)} /><Fundamental label="Earnings growth" value={percent(f.earnings_growth)} /></div><div className="subscore">Fundamental quality <strong>{Number(item.fundamental_score || 0).toFixed(0)}/100</strong></div></section>
      <section><h4>AI / quantitative prediction</h4><div className="prediction-box"><div><span>5D expected</span><strong className={Number(item.predicted_5d) >= 0 ? "positive" : "negative"}>{pct(item.predicted_5d)}</strong></div><div><span>20D expected</span><strong className={Number(item.predicted_20d) >= 0 ? "positive" : "negative"}>{pct(item.predicted_20d)}</strong></div><div><span>Model signal</span><strong>{item.model_signal || "—"}</strong></div><div><span>Model score</span><strong>{Number(item.model_score || 0).toFixed(0)}/100</strong></div></div><div className="subscore">Intelligence + event score <strong>{Number(item.score || 0).toFixed(0)}/100</strong></div></section>
    </div>

    <div className="entry-strip"><div><span>Current price</span><strong>{money(item.current_price)}</strong></div><div><span>Preferred accumulation zone</span><strong>{item.entry_low && item.entry_high ? `${money(item.entry_low)} – ${money(item.entry_high)}` : "Not enough fresh price data"}</strong></div><div className="invalidation"><span>What would invalidate the idea?</span><strong>{item.invalidation}</strong></div></div>

    {news.source_url && <div className="card-footer"><span>Evidence: {news.source || "market source"}</span><a href={news.source_url} target="_blank" rel="noreferrer">Read source →</a></div>}
  </article>;
}

function App() {
  const [recommendations, setRecommendations] = useState([]);
  const [news, setNews] = useState([]);
  const [categories, setCategories] = useState({});
  const [generatedAt, setGeneratedAt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      setError("");
      const [recData, intelligence] = await Promise.all([getRecommendations(5), getIntelligenceOverview(12)]);
      setRecommendations(recData.recommendations || []);
      setGeneratedAt(recData.generated_at);
      setNews(intelligence.news || []);
      setCategories(intelligence.categories || {});
    } catch (e) {
      console.error(e);
      setError("StockAgent could not load live intelligence. Make sure the backend is running.");
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
      <section className="intro"><div><div className="live"><i/> LIVE INTELLIGENCE</div><h2>What matters in the market <span>right now.</span></h2><p>StockAgent turns real-world events and news into a small number of evidence-backed stocks to consider. It does the filtering and reasoning; you get the shortlist.</p></div><div className="updated">{generatedAt ? `Updated ${new Date(generatedAt).toLocaleTimeString()}` : "Analyzing…"}</div></section>
      {error && <div className="error">{error}</div>}

      <section className="news-section">
        <div className="section-title"><div><h3>News & market intelligence</h3><p>Recent events StockAgent is watching and how they may affect the real economy.</p></div><span>{news.length} signals</span></div>
        <div className="category-strip">{Object.entries(categories).map(([name, count]) => <span key={name}>{label(name)} <b>{count}</b></span>)}</div>
        {loading ? <div className="empty">Loading live intelligence…</div> : news.length ? <div className="news-grid">{news.map((item) => <NewsCard key={item.event_id} item={item} />)}</div> : <div className="empty"><strong>No recent news events have been converted into market intelligence yet.</strong><p>Run Analyze now to ingest and interpret the latest available information.</p></div>}
      </section>

      <section className="recommendations">
        <div className="section-title"><div><h3>Stocks worth considering</h3><p>Maximum 5 ideas. These are the output of the intelligence pipeline—not a market-wide stock list.</p></div><span>{recommendations.length} ideas</span></div>
        {loading ? <div className="empty">Building recommendations…</div> : recommendations.length === 0 ? <div className="empty"><strong>No high-conviction recommendation yet.</strong><p>News can be important without creating a good entry. StockAgent only shows ideas when the evidence supports consideration.</p><button className="secondary" onClick={scan} disabled={running}>{running ? "Analyzing…" : "Analyze now"}</button></div> : recommendations.map((item) => <RecommendationCard key={`${item.symbol}-${item.rank}`} item={item} />)}
      </section>

      <section className="method"><h3>How StockAgent reaches the shortlist</h3><div className="method-flow"><span>News & events</span><b>→</b><span>Real-world impact</span><b>→</b><span>Sector / company exposure</span><b>→</b><span>Fundamentals</span><b>→</b><span>AI / ML prediction</span><b>→</b><strong>3–5 stocks to consider</strong></div></section>
    </main>
  </div>;
}

export default App;

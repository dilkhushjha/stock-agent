import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { getIntelligenceOverview, getRecommendations, runLiveAgent } from "./services/api";

const num = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const pct = (v) => num(v) === null ? "—" : `${num(v) >= 0 ? "+" : ""}${num(v).toFixed(2)}%`;
const money = (v) => num(v) === null ? "—" : `₹${num(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const percent = (v) => num(v) === null ? "—" : `${(num(v) * 100).toFixed(0)}%`;
const label = (v) => String(v || "Uncategorized").replaceAll("_", " ");

function Metric({ name, value }) { return <div className="metric"><span>{name}</span><strong>{value}</strong></div>; }

function NewsCard({ item }) {
  return <article className="news-card">
    <div className="news-meta"><span className="tag">{label(item.category)}</span><span>{item.source || "News source"}</span><span>{item.published_at ? new Date(item.published_at).toLocaleString() : ""}</span></div>
    <h4>{item.title}</h4>
    <p className="summary">{item.summary || "StockAgent is analysing this event for market relevance."}</p>
    <div className="impact-row">
      <Metric name="Sector" value={label(item.sector)} />
      <Metric name="Direction" value={label(item.direction)} />
      <Metric name="Impact" value={label(item.impact)} />
      <Metric name="Horizon" value={item.horizon || "—"} />
    </div>
    <div className="world-effect"><span>REAL-WORLD EFFECT</span><p>{item.real_world_effect || "This event is being evaluated for its economic and company-level consequences."}</p></div>
    {item.source_url && <a className="source" href={item.source_url} target="_blank" rel="noreferrer">Read source →</a>}
  </article>;
}

function Recommendation({ item }) {
  const f = item.fundamentals || {};
  const n = item.news || {};
  const e = item.event || {};
  return <article className="recommendation">
    <div className="rec-top">
      <div className="rank">#{item.rank}</div>
      <div className="rec-title"><div className="symbol"><h2>{item.symbol}</h2><span className={item.action === "BUY" ? "buy" : "watch"}>{item.action}</span></div><p>{item.company} · {item.sector || "Sector under analysis"}</p></div>
      <div className="conviction"><strong>{Number(item.score || 0).toFixed(0)}</strong><span>/100</span><small>conviction</small></div>
    </div>

    <div className="thesis"><span>WHY THIS STOCK?</span><h3>{item.thesis || "Evidence-backed opportunity"}</h3><p>{item.reason}</p></div>

    <div className="catalyst-grid">
      <div><span>NEWS / CATALYST</span><strong>{n.title || e.title || "Market event"}</strong><small>{n.source || item.evidence?.source || "StockAgent intelligence"}</small></div>
      <div><span>REAL-WORLD IMPACT</span><p>{e.description || item.why_now || "Event impact is being evaluated."}</p></div>
    </div>

    <div className="signals"><Metric name="Why now" value={item.why_now || "—"}/><Metric name="Risk" value={item.risk || "—"}/><Metric name="Horizon" value={item.horizon || "—"}/><Metric name="Confidence" value={percent(item.confidence)}/></div>

    <div className="evidence-heading"><h4>Evidence stack</h4><span>Intelligence + fundamentals + AI/ML</span></div>
    <div className="evidence-grid">
      <section><h5>Fundamentals</h5><div className="metric-grid"><Metric name="P/E" value={f.pe ?? "—"}/><Metric name="ROE" value={percent(f.roe)}/><Metric name="Debt / Equity" value={f.debt_to_equity ?? "—"}/><Metric name="Profit margin" value={percent(f.profit_margin)}/><Metric name="Revenue growth" value={percent(f.revenue_growth)}/><Metric name="Earnings growth" value={percent(f.earnings_growth)}/></div><div className="score-line">Fundamental quality <b>{Number(item.fundamental_score || 0).toFixed(0)}/100</b></div></section>
      <section><h5>AI / ML prediction</h5><div className="prediction"><Metric name="5D expected" value={<b className={num(item.predicted_5d) >= 0 ? "positive" : "negative"}>{pct(item.predicted_5d)}</b>}/><Metric name="20D expected" value={<b className={num(item.predicted_20d) >= 0 ? "positive" : "negative"}>{pct(item.predicted_20d)}</b>}/><Metric name="Signal" value={item.model_signal || "—"}/><Metric name="Model score" value={`${Number(item.model_score || 0).toFixed(0)}/100`}/></div><div className="score-line">Opportunity intelligence <b>{Number(item.evidence?.opportunity_score || item.score || 0).toFixed(0)}/100</b></div></section>
    </div>

    <div className="entry"><div><span>CURRENT PRICE</span><strong>{money(item.current_price)}</strong></div><div><span>PREFERRED ENTRY / ACCUMULATION</span><strong>{item.entry_low && item.entry_high ? `${money(item.entry_low)} – ${money(item.entry_high)}` : "Awaiting fresh price"}</strong></div><div><span>THESIS INVALIDATION</span><p>{item.invalidation}</p></div></div>
    {n.source_url && <div className="rec-footer"><span>Evidence: {n.source || "source"}</span><a href={n.source_url} target="_blank" rel="noreferrer">Read evidence →</a></div>}
  </article>;
}

function App() {
  const [recommendations, setRecommendations] = useState([]);
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState(null);

  async function load() {
    try {
      setError("");
      const [r, i] = await Promise.all([getRecommendations(5), getIntelligenceOverview(20)]);
      setRecommendations(r.recommendations || []);
      setNews(i.news || []);
      setUpdated(r.generated_at);
    } catch (e) {
      console.error(e);
      setError("Unable to load live intelligence. Check that the StockAgent backend is running.");
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); const t = setInterval(load, 60_000); return () => clearInterval(t); }, []);

  async function analyze() {
    try { setRunning(true); setError(""); await runLiveAgent(); await load(); }
    catch (e) { console.error(e); setError("Analysis failed. Check the backend console."); }
    finally { setRunning(false); }
  }

  const groups = useMemo(() => {
    const map = new Map();
    news.forEach((item) => {
      const key = item.sector || item.category || "Other market intelligence";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    });
    return [...map.entries()];
  }, [news]);

  return <div className="app">
    <header><div className="brand"><div className="logo">S</div><div><h1>StockAgent</h1><p>Real-world intelligence → stocks worth considering</p></div></div><button className="analyze" onClick={analyze} disabled={running}>{running ? "Analyzing…" : "Analyze now"}</button></header>
    <main>
      <section className="hero"><div><span className="eyebrow"><i/> LIVE MARKET INTELLIGENCE</span><h2>What matters <em>right now</em>.</h2><p>StockAgent filters the noise. It connects news and real-world events to sectors, companies, fundamentals and AI/ML predictions—then gives you a small shortlist to consider.</p></div><div className="refresh">{updated ? `Updated ${new Date(updated).toLocaleTimeString()}` : "Loading intelligence"}</div></section>
      {error && <div className="error">{error}</div>}

      <section className="intel-section">
        <div className="section-head"><div><span className="eyebrow">01 · MARKET INTELLIGENCE</span><h3>News, organized by sector</h3><p>Not just headlines. Each event is translated into the sector it may affect and its real-world consequence.</p></div><b>{news.length} signals</b></div>
        {loading ? <div className="empty">Loading intelligence…</div> : groups.length ? <div className="sector-groups">{groups.map(([sector, items]) => <div className="sector-group" key={sector}><div className="sector-head"><h4>{label(sector)}</h4><span>{items.length} {items.length === 1 ? "event" : "events"}</span></div><div className="news-grid">{items.map((item, i) => <NewsCard key={`${item.event_id || item.title}-${i}`} item={item}/>)}</div></div>)}</div> : <div className="empty"><strong>No market intelligence ready yet.</strong><p>Run Analyze now to ingest and interpret recent events.</p></div>}
      </section>

      <section className="ideas-section">
        <div className="section-head"><div><span className="eyebrow">02 · THE OUTPUT</span><h3>Stocks worth considering</h3><p>Only the few ideas that survive the evidence stack. This is not a market-wide stock list.</p></div><b>TOP {recommendations.length || 0}</b></div>
        {loading ? <div className="empty">Building recommendations…</div> : recommendations.length ? recommendations.map((item) => <Recommendation key={`${item.symbol}-${item.rank}`} item={item}/>) : <div className="empty"><strong>No high-conviction stock recommendation yet.</strong><p>An important news event does not automatically mean a stock is attractive. StockAgent waits for enough supporting evidence.</p><button className="secondary" onClick={analyze} disabled={running}>{running ? "Analyzing…" : "Analyze now"}</button></div>}
      </section>

      <section className="logic"><span className="eyebrow">HOW THE DECISION IS MADE</span><div><strong>News</strong><i>→</i><strong>Real-world effect</strong><i>→</i><strong>Sector exposure</strong><i>→</i><strong>Fundamentals</strong><i>→</i><strong>AI / ML</strong><i>→</i><strong>Few stocks</strong></div></section>
    </main>
  </div>;
}

export default App;

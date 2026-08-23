import { useEffect, useMemo, useState } from "react";
import "./App.css";
import "./Dashboard.css";
import "./CompactRecommendations.css";
import { getIntelligenceOverview, getRecommendations, runLiveAgent } from "./services/api";

const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : null);
const pct = (v) => num(v) === null ? "—" : `${num(v) >= 0 ? "+" : ""}${num(v).toFixed(2)}%`;
const money = (v) => num(v) === null ? "—" : `₹${num(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const percent = (v) => num(v) === null ? "—" : `${(num(v) * 100).toFixed(0)}%`;
const label = (v) => String(v || "Uncategorized").replaceAll("_", " ");
const dateTime = (v) => v ? new Date(v).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

function Metric({ name, value }) { return <div className="metric"><span>{name}</span><strong>{value}</strong></div>; }

function NewsTable({ items }) {
  return <div className="news-table-wrap"><table className="news-table"><thead><tr><th>Article</th><th>Category</th><th>Sector</th><th>Impact</th><th>Direction</th><th>Horizon</th><th>Source</th></tr></thead><tbody>
    {items.map((item, i) => <tr key={`${item.event_id || item.title}-${i}`}>
      <td className="article-cell">{item.source_url ? <a href={item.source_url} target="_blank" rel="noreferrer">{item.title}</a> : <strong>{item.title}</strong>}<small>{item.summary || "StockAgent is assessing this event."}</small><em>{dateTime(item.published_at)}</em></td>
      <td><span className="table-tag">{label(item.category)}</span></td><td><strong>{label(item.sector)}</strong></td>
      <td><span className={`impact impact-${String(item.impact || "").toLowerCase()}`}>{label(item.impact)}</span></td>
      <td>{label(item.direction)}</td><td>{item.horizon || "—"}</td><td>{item.source || "—"}</td>
    </tr>)}
  </tbody></table></div>;
}

function SectorInsight({ sector, items }) {
  const strongest = [...items].sort((a, b) => Number(b.confidence || 0) - Number(a.confidence || 0))[0];
  return <div className="sector-block"><div className="sector-title"><div><span>SECTOR INTELLIGENCE</span><h4>{label(sector)}</h4></div><b>{items.length} {items.length === 1 ? "signal" : "signals"}</b></div>
    {strongest && <div className="sector-insight"><span>RELEVANT INSIGHT</span><p>{strongest.real_world_effect || `StockAgent sees a potential ${label(strongest.direction)} effect on ${label(sector)}.`}</p><div><b>Confidence {percent(strongest.confidence)}</b><b>Impact {label(strongest.impact)}</b><b>Horizon {strongest.horizon || "—"}</b></div></div>}
    <NewsTable items={items} /></div>;
}

function CausalChain({ causal }) {
  if (!causal || !causal.chain) return null;
  const historical = causal.historical_reaction || {};
  return <div className="causal-panel">
    <div className="evidence-title"><span>CAUSE → EFFECT INTELLIGENCE</span><strong>{causal.normalized_entity || "Market event"}</strong></div>
    <div className="causal-chain"><b>News / event</b><i>→</i><b>Economic effect</b><i>→</i><b>Sector impact</b><i>→</i><b>Company exposure</b><i>→</i><b>Market response</b></div>
    <p className="causal-text">{causal.chain}</p>
    <p className="causal-benefit">{causal.benefit_logic}</p>
    <div className="causal-stats">
      <Metric name="Historical 5D avg" value={historical.avg_5d_return_pct == null ? "No comparable sample" : pct(historical.avg_5d_return_pct)} />
      <Metric name="Historical 5D median" value={historical.median_5d_return_pct == null ? "—" : pct(historical.median_5d_return_pct)} />
      <Metric name="Positive outcomes" value={historical.positive_outcome_rate_pct == null ? "—" : `${historical.positive_outcome_rate_pct.toFixed(1)}%`} />
      <Metric name="Comparable observations" value={historical.sample_count || 0} />
    </div>
  </div>;
}

function RecommendationModal({ item, onClose }) {
  const f = item.fundamentals || {}, n = item.news || {}, e = item.event || {}, causal = item.causal_intelligence || {};
  useEffect(() => { const h = (ev) => ev.key === "Escape" && onClose(); window.addEventListener("keydown", h); document.body.style.overflow = "hidden"; return () => { window.removeEventListener("keydown", h); document.body.style.overflow = ""; }; }, [onClose]);
  return <div className="modal-backdrop" onMouseDown={(ev) => ev.target === ev.currentTarget && onClose()}><div className="recommendation-modal">
    <div className="modal-header"><div className="rec-head"><div className="rank">#{item.rank}</div><div className="rec-name"><div><h2>{item.symbol}</h2><span className={item.action === "BUY" ? "buy" : "watch"}>{item.action}</span><span className={`priority-badge ${String(item.priority || "LOW").toLowerCase()}`}>{item.priority_label || `${item.priority || "LOW"} priority`}</span></div><p>{item.company} · {item.sector || "Sector under analysis"}</p></div><div className="conviction"><strong>{Number(item.score || 0).toFixed(0)}</strong><small>conviction / 100</small></div></div><button className="modal-close" onClick={onClose}>×</button></div>
    <div className="rec-thesis"><span>INVESTMENT THESIS</span><h3>{item.thesis || "Evidence-backed opportunity"}</h3><p>{item.reason || item.why_now || "Supporting evidence is being evaluated."}</p></div>
    <CausalChain causal={causal} />
    <div className="rec-intelligence"><div><span>CATALYST / NEWS</span>{n.source_url ? <a href={n.source_url} target="_blank" rel="noreferrer">{n.title || e.title || "Market event"}</a> : <strong>{n.title || e.title || "Market event"}</strong>}<small>{n.source || item.evidence?.source || "StockAgent intelligence"}</small></div><div><span>REAL-WORLD EFFECT</span><p>{e.description || item.why_now || "Event impact is being evaluated."}</p></div><div><span>WHY NOW</span><p>{item.why_now || "Fresh evidence is being evaluated."}</p></div></div>
    <div className="rec-stats"><Metric name="Priority" value={item.priority_label || item.priority || "—"}/><Metric name="Sector priority" value={item.sector_priority || "—"}/><Metric name="Exposure" value={item.exposure_strength == null ? "—" : percent(item.exposure_strength)}/><Metric name="Risk" value={item.risk || "—"}/><Metric name="Confidence" value={percent(item.confidence)}/></div>
    <div className="evidence"><div className="evidence-title"><span>EVIDENCE STACK</span><strong>Fundamentals + market behaviour + AI/ML + event intelligence</strong></div><div className="evidence-columns"><section><h5>Fundamentals</h5><div className="metric-grid"><Metric name="P/E" value={f.pe ?? "—"}/><Metric name="ROE" value={percent(f.roe)}/><Metric name="Debt / Equity" value={f.debt_to_equity ?? "—"}/><Metric name="Profit margin" value={percent(f.profit_margin)}/><Metric name="Revenue growth" value={percent(f.revenue_growth)}/><Metric name="Earnings growth" value={percent(f.earnings_growth)}/><Metric name="Market cap" value={f.market_cap ? money(f.market_cap) : "—"}/><Metric name="P/B" value={f.pb ?? "—"}/></div></section><section><h5>AI / ML & market</h5><div className="metric-grid"><Metric name="5D expected" value={<b className={num(item.predicted_5d) >= 0 ? "positive" : "negative"}>{pct(item.predicted_5d)}</b>}/><Metric name="20D expected" value={<b className={num(item.predicted_20d) >= 0 ? "positive" : "negative"}>{pct(item.predicted_20d)}</b>}/><Metric name="Signal" value={item.model_signal || "—"}/><Metric name="Model score" value={`${Number(item.model_score || 0).toFixed(0)}/100`}/><Metric name="1D return" value={pct(item.market?.return_1d_pct)}/><Metric name="20D return" value={pct(item.market?.return_20d_pct)}/><Metric name="Volume vs avg" value={item.market?.volume_vs_20d_avg ? `${Number(item.market.volume_vs_20d_avg).toFixed(2)}×` : "—"}/><Metric name="52W position" value={item.market?.distance_from_52w_high_pct ? pct(item.market.distance_from_52w_high_pct) : "—"}/></div></section></div></div>
    <div className="entry-row"><div><span>CURRENT PRICE</span><strong>{money(item.current_price)}</strong></div><div><span>PREFERRED ENTRY / ACCUMULATION</span><strong>{item.entry_low && item.entry_high ? `${money(item.entry_low)} – ${money(item.entry_high)}` : "Awaiting fresh price"}</strong></div><div><span>THESIS INVALIDATION</span><p>{item.invalidation || "Reassess if the catalyst weakens or valuation/risk changes materially."}</p></div></div>
    {n.source_url && <div className="rec-source"><span>Primary evidence: {n.source || "news source"}</span><a href={n.source_url} target="_blank" rel="noreferrer">Read article →</a></div>}
  </div></div>;
}

function RecommendationCard({ item, onClick }) { return <button className={`recommendation compact-card priority-${String(item.priority || "LOW").toLowerCase()}`} onClick={onClick}><div className="compact-rank">#{item.rank}</div><div className="compact-main"><div className="compact-title"><strong>{item.symbol}</strong><span className={item.action === "BUY" ? "buy" : "watch"}>{item.action}</span><span className={`priority-badge ${String(item.priority || "LOW").toLowerCase()}`}>{item.priority || "LOW"}</span></div><p>{item.company} · {item.sector || "Market"}</p><small>{item.thesis || item.reason || "Evidence-backed opportunity"}</small></div><div className="compact-score"><strong>{Number(item.score || 0).toFixed(0)}</strong><span>/100</span></div><div className="compact-arrow">→</div></button>; }

function App() {
  const [recommendations, setRecommendations] = useState([]), [news, setNews] = useState([]), [loading, setLoading] = useState(true), [running, setRunning] = useState(false), [error, setError] = useState(""), [updated, setUpdated] = useState(null), [selected, setSelected] = useState(null);
  async function load() { try { setError(""); const [r, i] = await Promise.all([getRecommendations(5), getIntelligenceOverview(20)]); setRecommendations(r.recommendations || []); setNews(i.news || []); setUpdated(r.generated_at); } catch (e) { console.error(e); setError("Unable to load live intelligence. Check that the StockAgent backend is running."); } finally { setLoading(false); } }
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, []);
  async function analyze() { try { setRunning(true); setError(""); await runLiveAgent(); await load(); } catch (e) { console.error(e); setError("Analysis failed. Check the backend console."); } finally { setRunning(false); } }
  const groups = useMemo(() => { const map = new Map(); news.forEach((item) => { const key = item.sector || item.category || "Other market intelligence"; if (!map.has(key)) map.set(key, []); map.get(key).push(item); }); return [...map.entries()].sort((a, b) => b[1].length - a[1].length); }, [news]);
  const priorityCounts = useMemo(() => recommendations.reduce((a, r) => { const p = r.priority || "LOW"; a[p] = (a[p] || 0) + 1; return a; }, {}), [recommendations]);
  return <div className="app"><header className="navbar"><div className="brand"><div className="logo">S</div><div><h1>StockAgent</h1><p>Real-world intelligence → stocks worth considering</p></div></div><div className="nav-right"><span className="live-dot">LIVE</span><button className="analyze" onClick={analyze} disabled={running}>{running ? "Analyzing…" : "Analyze now"}</button></div></header><main>
    <section className="hero"><div><span className="eyebrow"><i /> LIVE MARKET INTELLIGENCE</span><h2>What matters <em>right now</em>.</h2><p>StockAgent connects news, real-world events, sector impact, company fundamentals, market behaviour and AI/ML predictions to produce a small set of stocks worth considering.</p></div><div className="refresh">{updated ? `Updated ${new Date(updated).toLocaleTimeString()}` : "Loading intelligence"}</div></section>
    {error && <div className="error">{error}</div>}
    <section className="section"><div className="section-head"><div><span className="eyebrow">01 · NEWS & INTELLIGENCE</span><h3>What is happening, by sector</h3><p>News is grouped by sector, then interpreted for real-world consequences before stock selection.</p></div><b>{news.length} signals</b></div>{loading ? <div className="empty">Loading intelligence…</div> : groups.length ? groups.map(([sector, items]) => <SectorInsight key={sector} sector={sector} items={items}/>) : <div className="empty"><strong>No market intelligence ready yet.</strong><p>Run Analyze now to ingest and interpret recent events.</p></div>}</section>
    <section className="section recommendations-section"><div className="section-head"><div><span className="eyebrow">02 · STOCK SELECTION</span><h3>Stocks worth considering</h3><p>Priority is driven by event relevance, direct sector exposure, evidence, fundamentals, market behaviour and AI/ML confirmation.</p></div><div className="priority-summary"><span>HIGH {priorityCounts.HIGH || 0}</span><span>MEDIUM {priorityCounts.MEDIUM || 0}</span><span>LOW {priorityCounts.LOW || 0}</span></div></div>{loading ? <div className="empty">Building recommendations…</div> : recommendations.length ? <div className="recommendation-grid">{recommendations.map(item => <RecommendationCard key={`${item.symbol}-${item.rank}`} item={item} onClick={() => setSelected(item)}/>)}</div> : <div className="empty"><strong>No qualifying recommendation yet.</strong><p>StockAgent will not manufacture a BUY. It waits for supporting intelligence, fundamentals, market evidence and model confirmation.</p><button className="secondary" onClick={analyze} disabled={running}>{running ? "Analyzing…" : "Analyze now"}</button></div>}</section>
    <section className="logic"><span className="eyebrow">DECISION LOGIC</span><div><strong>News</strong><i>→</i><strong>Cause / effect</strong><i>→</i><strong>Sector</strong><i>→</i><strong>Direct exposure</strong><i>→</i><strong>Historical response</strong><i>→</i><strong>Fundamentals</strong><i>→</i><strong>AI / ML</strong><i>→</i><strong>Priority</strong><i>→</i><strong>Few stocks</strong></div></section>
  </main><footer><span>StockAgent · evidence-first market intelligence</span><span>Not financial advice</span></footer>{selected && <RecommendationModal item={selected} onClose={() => setSelected(null)}/>}</div>;
}
export default App;

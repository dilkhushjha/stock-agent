import { useMemo } from "react";
import "./SectorCards.css";

const n = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const pct = (v) => n(v) === null ? "—" : `${n(v) >= 0 ? "+" : ""}${n(v).toFixed(2)}%`;
const label = (v) => String(v || "Other").replaceAll("_", " ");
const percent = (v) => n(v) === null ? "—" : `${(n(v) * 100).toFixed(0)}%`;

function SectorCard({ sector, items, recommendations, rank, score }) {
  const recs = recommendations.filter(r => label(r.sector).toLowerCase() === label(sector).toLowerCase());
  const strongest = [...items].sort((a,b) => Number(b.confidence||0) - Number(a.confidence||0))[0];
  const predictions = recs.map(r => n(r.predicted_5d)).filter(v => v !== null);
  const avgPrediction = predictions.length ? predictions.reduce((a,b)=>a+b,0)/predictions.length : null;
  const confidence = items.map(x=>n(x.confidence)).filter(v=>v!==null);
  const avgConfidence = confidence.length ? confidence.reduce((a,b)=>a+b,0)/confidence.length : null;
  const highImpact = items.filter(x=>["HIGH","SEVERE"].includes(String(x.impact||"").toUpperCase())).length;
  const stocks = recs.slice(0,3).map(r=>r.symbol);
  const reasons = [strongest?.title, strongest?.real_world_effect || strongest?.summary, strongest?.direction || strongest?.impact ? `${label(strongest.direction)}${strongest.impact ? ` · ${label(strongest.impact)}` : ""}` : null].filter(Boolean).slice(0,3);
  const top = rank === 1;
  return <button type="button" className={`sector-card ${top ? "sector-card-top" : ""}`} onClick={() => window.dispatchEvent(new CustomEvent("stockagent:sector", { detail: { sector } }))}>
    <div className="sector-card-topline"><div className="sector-rank">#{rank}</div><div className="sector-card-heading"><span>SECTOR</span><h4>{label(sector)}</h4></div><div className="sector-activity"><small>PRIORITY</small><strong>{score}</strong><em>/100</em></div></div>
    {top && <div className="sector-top-badge">TOP SECTOR SIGNAL</div>}
    <div className="sector-card-summary"><strong>{strongest?.real_world_effect || strongest?.title || "Active sector signal"}</strong></div>
    <div className="sector-card-metrics"><div><span>NEWS</span><strong>{items.length}</strong></div><div><span>CONFIDENCE</span><strong>{percent(avgConfidence)}</strong></div><div><span>5D SIGNAL</span><strong className={avgPrediction===null?"":avgPrediction>=0?"positive":"negative"}>{pct(avgPrediction)}</strong></div><div><span>HIGH IMPACT</span><strong>{highImpact}</strong></div></div>
    <div className="sector-card-effect"><span>WHY THIS SECTOR</span><ul>{reasons.length ? reasons.map((r,i)=><li key={i}>{r}</li>) : <li>Current news and market signals are being evaluated.</li>}</ul></div>
    <div className="sector-card-footer"><div><span>STOCKS IDENTIFIED</span><strong>{stocks.length ? stocks.join(" · ") : "No qualified stock yet"}</strong></div><div><span>STATUS</span><strong className={top?"sector-priority-high":""}>{top?"HIGHEST PRIORITY":rank<=3?"WATCH":"MONITOR"}</strong></div></div>
  </button>;
}

export default function SectorCards({ groups, recommendations }) {
  const ranked = useMemo(() => groups.map(([sector,items]) => {
    const recs = recommendations.filter(r=>label(r.sector).toLowerCase()===label(sector).toLowerCase());
    const conf = items.map(x=>n(x.confidence)).filter(v=>v!==null);
    const avgConf = conf.length?conf.reduce((a,b)=>a+b,0)/conf.length:0;
    const pred = recs.map(r=>n(r.predicted_5d)).filter(v=>v!==null);
    const avgPred = pred.length?pred.reduce((a,b)=>a+b,0)/pred.length:0;
    const high = items.filter(x=>["HIGH","SEVERE"].includes(String(x.impact||"").toUpperCase())).length;
    const directional = items.filter(x=>/positive|bull/i.test(String(x.direction||""))).length;
    const score = Math.min(100, Math.round(items.length*10 + high*18 + directional*7 + avgConf*35 + Math.max(0,avgPred)*2));
    return {sector,items,recs,score};
  }).sort((a,b)=>b.score-a.score),[groups,recommendations]);
  return <div className="sector-cards-grid">{ranked.map((x,i)=><SectorCard key={x.sector} {...x} rank={i+1} recommendations={recommendations}/>)}</div>;
}

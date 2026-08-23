import { useMemo } from "react";
import "./SectorCards.css";

const n = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const pct = (v) => n(v) === null ? "—" : `${n(v) >= 0 ? "+" : ""}${n(v).toFixed(2)}%`;
const label = (v) => String(v || "Uncategorized").replaceAll("_", " ");
const percent = (v) => n(v) === null ? "—" : `${(n(v) * 100).toFixed(0)}%`;

function SectorCard({ sector, items, recommendations = [], rank }) {
  const strongest = [...items].sort((a, b) => Number(b.confidence || 0) - Number(a.confidence || 0))[0];
  const sectorRecs = recommendations.filter((r) => label(r.sector).toLowerCase() === label(sector).toLowerCase());
  const predicted = sectorRecs.map((r) => n(r.predicted_5d)).filter((v) => v !== null);
  const avgPrediction = predicted.length ? predicted.reduce((a, b) => a + b, 0) / predicted.length : null;
  const confidence = items.map((x) => n(x.confidence)).filter((v) => v !== null);
  const avgConfidence = confidence.length ? confidence.reduce((a, b) => a + b, 0) / confidence.length : null;
  const highImpact = items.filter((x) => ["HIGH", "SEVERE"].includes(String(x.impact || "").toUpperCase())).length;
  const positive = items.filter((x) => /positive|bull/i.test(String(x.direction || ""))).length;
  const activityScore = Math.round(Math.min(100, items.length * 12 + highImpact * 14 + positive * 6 + (avgConfidence || 0) * 35 + Math.max(0, avgPrediction || 0) * 2));
  const topStocks = sectorRecs.slice(0, 3).map((r) => r.symbol).join(" · ");
  const reasons = [
    strongest?.title ? `Trigger: ${strongest.title}` : null,
    strongest?.real_world_effect ? `Why it matters: ${strongest.real_world_effect}` : null,
    strongest?.direction || strongest?.impact ? `Signal: ${label(strongest.direction)} ${strongest.impact ? `· ${label(strongest.impact)} impact` : ""}` : null,
    sectorRecs.length ? `Exposed candidates: ${sectorRecs.slice(0, 3).map((r) => r.symbol).join(", ")}` : null,
  ].filter(Boolean);

  return <article className={`sector-card ${rank === 1 ? "sector-card-top" : ""}`}>
    <div className="sector-card-topline"><div className="sector-rank">#{rank}</div><div className="sector-card-heading"><span>SECTOR SIGNAL</span><h4>{label(sector)}</h4></div><div className="sector-activity"><small>ACTIVITY</small><strong>{activityScore}</strong><em>/100</em></div></div>
    <div className="sector-card-summary"><strong>{strongest?.real_world_effect || `Multiple signals are currently affecting ${label(sector)}.`}</strong><p>{strongest?.summary || strongest?.title || "StockAgent is correlating current news, market activity and company exposure."}</p></div>
    <div className="sector-card-metrics"><div><span>NEWS</span><strong>{items.length}</strong><small>signals</small></div><div><span>CONFIDENCE</span><strong>{percent(avgConfidence)}</strong><small>average</small></div><div><span>5D MODEL</span><strong className={avgPrediction !== null && avgPrediction >= 0 ? "positive" : avgPrediction !== null ? "negative" : ""}>{pct(avgPrediction)}</strong><small>available exposed stocks</small></div><div><span>HIGH IMPACT</span><strong>{highImpact}</strong><small>events</small></div></div>
    <div className="sector-card-effect"><span>WHY THIS SECTOR IS RANKED HERE</span>{reasons.length ? <ul>{reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul> : <p>Ranking is based on current news activity, event impact, confidence, direction and available stock signals.</p>}</div>
    <div className="sector-card-footer"><div><span>STOCKS CURRENTLY IDENTIFIED</span><strong>{topStocks || "No shortlisted stock yet — exposure scan continues"}</strong></div><div><span>PRIORITY</span><strong className={rank === 1 ? "sector-priority-high" : ""}>{rank === 1 ? "MOST ACTIVE" : rank <= 3 ? "WATCH" : "MONITOR"}</strong></div></div>
  </article>;
}

export default function SectorCards({ groups, recommendations }) {
  const ranked = useMemo(() => groups.map(([sector, items]) => {
    const recs = recommendations.filter((r) => label(r.sector).toLowerCase() === label(sector).toLowerCase());
    const confidence = items.map((x) => n(x.confidence)).filter((v) => v !== null);
    const avgConfidence = confidence.length ? confidence.reduce((a, b) => a + b, 0) / confidence.length : 0;
    const predicted = recs.map((r) => n(r.predicted_5d)).filter((v) => v !== null);
    const avgPrediction = predicted.length ? predicted.reduce((a, b) => a + b, 0) / predicted.length : 0;
    const high = items.filter((x) => ["HIGH", "SEVERE"].includes(String(x.impact || "").toUpperCase())).length;
    const directional = items.filter((x) => /positive|bull/i.test(String(x.direction || ""))).length;
    const score = items.length * 12 + high * 14 + directional * 6 + avgConfidence * 35 + Math.max(0, avgPrediction) * 2;
    return { sector, items, score };
  }).sort((a, b) => b.score - a.score), [groups, recommendations]);
  return <div className="sector-cards-grid">{ranked.map((item, index) => <SectorCard key={item.sector} {...item} rank={index + 1} recommendations={recommendations}/>)}</div>;
}

from __future__ import annotations

from datetime import datetime, timedelta
import re
from statistics import median

from sqlalchemy import select

from app.models.event import MarketEvent
from app.models.market_data import MarketData


_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "after", "before", "market",
    "stock", "stocks", "india", "indian", "sector", "company", "announces",
    "announced", "news", "new", "to", "of", "in", "on", "a", "an", "is",
}


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) >= 4 and token not in _STOPWORDS
    }


def _similarity(current: MarketEvent, candidate: MarketEvent) -> float:
    score = 0.0
    if current.sector and candidate.sector and str(current.sector).strip().upper() == str(candidate.sector).strip().upper():
        score += 0.45
    if current.event_type and candidate.event_type and str(current.event_type).strip().upper() == str(candidate.event_type).strip().upper():
        score += 0.30
    left = _tokens(f"{current.title} {current.entity}")
    right = _tokens(f"{candidate.title} {candidate.entity}")
    if left and right:
        score += 0.25 * (len(left & right) / max(1, len(left | right)))
    return min(1.0, score)


def _close_after(rows, start, days):
    target = start + timedelta(days=days)
    eligible = [r for r in rows if r.timestamp and r.timestamp >= target and r.close is not None]
    return eligible[0] if eligible else None


def _reaction(db, stock_id: int, event_date: datetime) -> dict:
    rows = db.scalars(
        select(MarketData)
        .where(MarketData.stock_id == stock_id, MarketData.timestamp >= event_date - timedelta(days=2), MarketData.timestamp <= event_date + timedelta(days=35))
        .order_by(MarketData.timestamp.asc())
    ).all()
    if not rows:
        return {}
    anchor = next((r for r in rows if r.timestamp and r.timestamp.date() >= event_date.date()), None)
    if not anchor or not anchor.close:
        return {}
    result = {}
    for days in (1, 5, 10, 20):
        end = _close_after(rows, anchor.timestamp, days)
        if end and end.close:
            result[f"return_{days}d_pct"] = round((float(end.close) / float(anchor.close) - 1) * 100, 2)
    return result


def find_historical_analogues(db, event: MarketEvent | None, stock_id: int | None = None, limit: int = 8) -> dict:
    if not event or not event.event_date:
        return {"available": False, "sample_count": 0, "observations": [], "summary": None}

    candidates = db.scalars(
        select(MarketEvent)
        .where(
            MarketEvent.id != event.id,
            MarketEvent.event_date.is_not(None),
            MarketEvent.event_date < event.event_date,
        )
        .order_by(MarketEvent.event_date.desc())
        .limit(500)
    ).all()

    ranked = sorted(
        ((candidate, _similarity(event, candidate)) for candidate in candidates),
        key=lambda pair: (-pair[1], pair[0].event_date),
    )
    ranked = [pair for pair in ranked if pair[1] >= 0.45][:limit]

    observations = []
    returns_5d = []
    returns_10d = []
    positive_5d = 0

    for candidate, similarity in ranked:
        reaction = _reaction(db, stock_id, candidate.event_date) if stock_id else {}
        r5 = reaction.get("return_5d_pct")
        r10 = reaction.get("return_10d_pct")
        if r5 is not None:
            returns_5d.append(r5)
            positive_5d += int(r5 > 0)
        if r10 is not None:
            returns_10d.append(r10)
        observations.append({
            "event_id": candidate.id,
            "date": candidate.event_date.isoformat(),
            "title": candidate.title,
            "event_type": candidate.event_type,
            "sector": candidate.sector,
            "direction": candidate.direction,
            "impact": candidate.impact,
            "similarity": round(similarity, 2),
            "stock_reaction": reaction,
        })

    summary = None
    if returns_5d:
        summary = {
            "median_5d_return_pct": round(median(returns_5d), 2),
            "average_5d_return_pct": round(sum(returns_5d) / len(returns_5d), 2),
            "positive_5d_rate_pct": round(positive_5d / len(returns_5d) * 100, 1),
            "median_10d_return_pct": round(median(returns_10d), 2) if returns_10d else None,
        }

    return {
        "available": bool(observations),
        "sample_count": len(observations),
        "observations": observations,
        "summary": summary,
        "method": "sector + event-type + title/entity similarity; forward stock returns from historical event date",
    }

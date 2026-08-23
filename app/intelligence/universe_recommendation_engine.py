from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.intelligence.recommendation_engine import RecommendationEngine
from app.models.event import MarketEvent
from app.models.market_data import MarketData
from app.models.stock import Stock


class UniverseRecommendationEngine:
    """Rank the broad NSE universe by sector activity, then stock evidence."""

    UNIVERSE_LIMIT = 2500
    PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    @classmethod
    def build(cls, db, limit: int = 10) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(days=14)
        stocks = db.scalars(
            select(Stock)
            .where(Stock.is_active.is_(True), Stock.sector.is_not(None))
            .order_by(Stock.symbol)
            .limit(cls.UNIVERSE_LIMIT)
        ).all()

        market_stock_ids = set(db.scalars(select(MarketData.stock_id).distinct()).all())
        stocks = [s for s in stocks if s.id in market_stock_ids]

        events = db.scalars(
            select(MarketEvent)
            .where(MarketEvent.event_date >= cutoff)
            .order_by(MarketEvent.event_date.desc())
            .limit(500)
        ).all()
        sector_stats = cls._sector_stats(events)
        recent_sectors = set(sector_stats)
        candidates = []

        for stock in stocks:
            try:
                item = RecommendationEngine._from_stock(
                    db, stock.symbol, recent_sectors=recent_sectors, cutoff=cutoff
                )
                if not item:
                    continue
                sector = str(item.get("sector") or stock.sector or "OTHER").strip().upper()
                ss = sector_stats.get(sector, cls._empty_sector())
                stock_score = float(item.get("score") or 0)
                sector_score = ss["score"]
                item["pre_sector_score"] = stock_score
                item["sector_score"] = sector_score
                item["score"] = round(min(100, stock_score * 0.82 + sector_score * 0.18), 1)
                item["sector_signal_count"] = ss["count"]
                item["sector_high_impact_count"] = ss["high_impact"]
                item["sector_latest_event"] = ss["latest_title"]
                item["sector_priority"] = cls._sector_priority(sector_score)
                item["universe_scanned"] = len(stocks)
                item["prediction_coverage"] = "TRAINED_MODEL" if item.get("predicted_5d") is not None else "NO_STOCK_MODEL"
                item["evidence_reasons"] = cls._reasons(item, ss)
                candidates.append(item)
            except Exception:
                continue

        sector_order = sorted(sector_stats.items(), key=lambda x: (-x[1]["score"], x[0]))
        sector_ranks = {sector: rank for rank, (sector, _) in enumerate(sector_order, 1)}
        for item in candidates:
            sector = str(item.get("sector") or "OTHER").strip().upper()
            item["sector_rank"] = sector_ranks.get(sector, len(sector_ranks) + 1)

        candidates.sort(key=lambda x: (
            cls.PRIORITY_ORDER.get(x.get("priority"), 3),
            x.get("sector_rank", 999),
            -float(x.get("score") or 0),
        ))
        selected = candidates[:limit]
        for rank, item in enumerate(selected, 1):
            item["rank"] = rank
        return selected

    @staticmethod
    def _empty_sector():
        return {"score": 20.0, "count": 0, "high_impact": 0, "positive": 0, "latest_title": None}

    @staticmethod
    def _sector_stats(events):
        grouped = {}
        for event in events:
            if event.sector:
                grouped.setdefault(str(event.sector).strip().upper(), []).append(event)
        result = {}
        for sector, rows in grouped.items():
            high = sum(str(e.impact or "").upper() in {"HIGH", "SEVERE"} for e in rows)
            positive = sum(str(e.direction or "").upper() in {"POSITIVE", "BULLISH"} for e in rows)
            negative = sum(str(e.direction or "").upper() in {"NEGATIVE", "BEARISH"} for e in rows)
            score = min(100, 35 + min(15, len(rows) * 2) + min(30, high * 10 + max(0, len(rows) - high) * 3) + min(20, positive * 5) - min(12, negative * 4))
            result[sector] = {"score": round(score, 1), "count": len(rows), "high_impact": high, "positive": positive, "latest_title": rows[0].title}
        return result

    @staticmethod
    def _sector_priority(score):
        return "HIGH" if score >= 75 else "MEDIUM" if score >= 55 else "LOW"

    @staticmethod
    def _reasons(item, ss):
        reasons = []
        news, event, market = item.get("news") or {}, item.get("event") or {}, item.get("market") or {}
        if news.get("title"): reasons.append(f"Catalyst: {news['title']}")
        if event.get("description"): reasons.append(f"Cause → effect: {event['description']}")
        elif event.get("sector"): reasons.append(f"Affected sector: {event['sector']}")
        if ss.get("count"): reasons.append(f"Sector activity: {ss['count']} signals; {ss['high_impact']} high-impact")
        if market.get("return_5d_pct") is not None: reasons.append(f"5D return: {float(market['return_5d_pct']):+.2f}%")
        if market.get("volume_vs_20d_avg") is not None: reasons.append(f"Volume: {float(market['volume_vs_20d_avg']):.2f}x 20D avg")
        if item.get("fundamental_score") is not None: reasons.append(f"Fundamentals: {float(item['fundamental_score']):.0f}/100")
        if item.get("predicted_5d") is not None: reasons.append(f"ML 5D: {float(item['predicted_5d']):+.2f}%")
        return reasons[:8]

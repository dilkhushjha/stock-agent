from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.intelligence.recommendation_engine import RecommendationEngine
from app.models.market_data import MarketData
from app.models.stock import Stock


class UniverseRecommendationEngine:
    """Run the existing evidence scorer across the whole active stock universe.

    The dashboard limit is intentionally separate from the scan universe. A
    request for 5 recommendations must not mean that only 5 stocks are ever
    considered. This service scans up to 2,500 active NSE equities that have
    market data, then returns the strongest few.
    """

    UNIVERSE_LIMIT = 2500

    @classmethod
    def build(cls, db, limit: int = 10) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(days=14)
        recent_events = db.execute(
            select(Stock.id, Stock.sector)
            .join(MarketData, MarketData.stock_id == Stock.id)
            .where(Stock.is_active.is_(True), Stock.sector != "INDEX")
            .distinct()
            .order_by(Stock.symbol)
            .limit(cls.UNIVERSE_LIMIT)
        ).all()

        recent_sectors = {
            str(sector).strip().upper()
            for _, sector in recent_events
            if sector
        }

        candidates: list[dict] = []
        for stock_id, _sector in recent_events:
            stock = db.get(Stock, stock_id)
            if not stock:
                continue
            try:
                item = RecommendationEngine._from_stock(
                    db,
                    stock.symbol,
                    recent_sectors=recent_sectors,
                    cutoff=cutoff,
                )
                if item:
                    item["universe_scanned"] = len(recent_events)
                    item["prediction_coverage"] = "TRAINED_MODEL" if item.get("predicted_5d") is not None else "NO_STOCK_MODEL"
                    item["evidence_reasons"] = cls._reasons(item)
                    candidates.append(item)
            except Exception:
                # One stale/malformed stock must never prevent the universe scan.
                continue

        candidates.sort(
            key=lambda x: (
                {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(x.get("priority"), 3),
                -float(x.get("score") or 0),
            )
        )

        selected = candidates[:limit]
        for rank, item in enumerate(selected, 1):
            item["rank"] = rank
        return selected

    @staticmethod
    def _reasons(item: dict) -> list[str]:
        reasons = []
        event = item.get("event") or {}
        news = item.get("news") or {}
        market = item.get("market") or {}
        fundamentals = item.get("fundamentals") or {}

        if news.get("title"):
            reasons.append(f"News catalyst: {news['title']}")
        if event.get("description"):
            reasons.append(f"Real-world effect: {event['description']}")
        elif event.get("sector"):
            reasons.append(f"Sector exposure: {event['sector']} is currently affected by the detected event")
        if event.get("direction") or event.get("impact"):
            reasons.append(
                f"Event signal: {event.get('direction') or 'UNCLASSIFIED'} / {event.get('impact') or 'UNCLASSIFIED'}"
            )
        if item.get("fundamental_score") is not None:
            reasons.append(f"Fundamentals score: {float(item['fundamental_score']):.0f}/100")
        if market.get("return_5d_pct") is not None:
            reasons.append(f"Recent 5D price behaviour: {float(market['return_5d_pct']):+.2f}%")
        if market.get("volume_vs_20d_avg") is not None:
            reasons.append(f"Volume vs 20D average: {float(market['volume_vs_20d_avg']):.2f}x")
        if item.get("predicted_5d") is not None:
            reasons.append(f"Trained model 5D expectation: {float(item['predicted_5d']):+.2f}%")
        else:
            reasons.append("Stock-specific trained-model prediction is not yet available for this candidate")

        return reasons[:8]

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.intelligence.opportunity_engine import OpportunityEngine
from app.intelligence.recommendation_engine import RecommendationEngine
from app.models.event import MarketEvent
from app.models.market_data import MarketData
from app.models.stock import Stock


class UniverseRecommendationEngine:
    """Rank the broad NSE universe using context-aware opportunity intelligence."""

    UNIVERSE_LIMIT = 2500
    PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    MAX_STOCKS_PER_SECTOR = 3

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

                # Preserve the event's real classification so the opportunity
                # engine can choose context-specific evidence weights.
                event_id = (item.get("evidence") or {}).get("event_id")
                event = next((e for e in events if e.id == event_id), None)
                if event:
                    item.setdefault("event", {})["event_type"] = event.event_type
                    item["event"]["confidence"] = event.confidence

                sector = str(item.get("sector") or stock.sector or "OTHER").strip().upper()
                ss = sector_stats.get(sector, cls._empty_sector())

                # First calculate the stock-level opportunity using context-aware
                # weights rather than a fixed 40/20/18/12/10 formula.
                opportunity = OpportunityEngine.score(item)
                stock_score = float(opportunity["score"])
                sector_score = ss["score"]

                # Sector impact matters more when there is a strong event. Keep
                # the blend bounded so a noisy sector cannot overwhelm company evidence.
                sector_weight = 0.25 if ss["high_impact"] > 0 else (0.20 if ss["count"] >= 3 else 0.14)
                final_score = stock_score * (1.0 - sector_weight) + sector_score * sector_weight

                item["pre_sector_score"] = round(stock_score, 1)
                item["sector_score"] = sector_score
                item["sector_weight"] = round(sector_weight, 2)
                item["score"] = round(min(100, final_score), 1)
                item["opportunity_intelligence"] = opportunity
                item["sector_signal_count"] = ss["count"]
                item["sector_high_impact_count"] = ss["high_impact"]
                item["sector_latest_event"] = ss["latest_title"]
                item["sector_priority"] = cls._sector_priority(sector_score)
                item["universe_scanned"] = len(stocks)
                item["prediction_coverage"] = "TRAINED_MODEL" if item.get("predicted_5d") is not None else "NO_STOCK_MODEL"
                item["evidence_reasons"] = cls._reasons(item, ss)
                item["priority"] = cls._priority(item)
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

        selected = []
        sector_counts = {}
        for item in candidates:
            sector = str(item.get("sector") or "OTHER").strip().upper()
            if sector_counts.get(sector, 0) >= cls.MAX_STOCKS_PER_SECTOR:
                continue
            selected.append(item)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            if len(selected) >= limit:
                break

        if len(selected) < limit:
            selected_symbols = {x.get("symbol") for x in selected}
            for item in candidates:
                if item.get("symbol") in selected_symbols:
                    continue
                selected.append(item)
                selected_symbols.add(item.get("symbol"))
                if len(selected) >= limit:
                    break

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
            high = sum(str(e.impact or "").upper() in {"HIGH", "SEVERE", "CRITICAL"} for e in rows)
            positive = sum(str(e.direction or "").upper() in {"POSITIVE", "BULLISH"} for e in rows)
            negative = sum(str(e.direction or "").upper() in {"NEGATIVE", "BEARISH"} for e in rows)
            confidence_values = [float(e.confidence) for e in rows if e.confidence is not None]
            confidence = (sum(confidence_values) / len(confidence_values)) if confidence_values else 0.5
            recency = max(0, 14 - ((datetime.utcnow() - (rows[0].event_date or datetime.utcnow())).total_seconds() / 86400)) / 14
            score = 30 + min(14, len(rows) * 2) + min(30, high * 10 + max(0, len(rows) - high) * 3)
            score += min(14, positive * 4) - min(14, negative * 5)
            score += confidence * 10 + recency * 8
            result[sector] = {
                "score": round(max(0, min(100, score)), 1),
                "count": len(rows),
                "high_impact": high,
                "positive": positive,
                "negative": negative,
                "confidence": round(confidence, 3),
                "latest_title": rows[0].title,
            }
        return result

    @staticmethod
    def _sector_priority(score):
        return "HIGH" if score >= 75 else "MEDIUM" if score >= 55 else "LOW"

    @staticmethod
    def _priority(item):
        score = float(item.get("score") or 0)
        intelligence = float(item.get("intelligence_score") or 0)
        fundamental = float(item.get("fundamental_score") or 0)
        opportunity = item.get("opportunity_intelligence") or {}
        probability = float(opportunity.get("estimated_target_probability_20d_pct") or 0)
        risk_reward = float(opportunity.get("risk_reward") or 0)

        if score >= 82 and intelligence >= 65 and fundamental >= 55 and probability >= 65 and risk_reward >= 1.8:
            return "HIGH"
        if score >= 62 and (intelligence >= 50 or probability >= 55) and risk_reward >= 1.2:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _reasons(item, ss):
        reasons = []
        news, event, market = item.get("news") or {}, item.get("event") or {}, item.get("market") or {}
        opportunity = item.get("opportunity_intelligence") or {}
        if news.get("title"):
            reasons.append(f"Catalyst: {news['title']}")
        if event.get("description"):
            reasons.append(f"Cause → effect: {event['description']}")
        elif event.get("sector"):
            reasons.append(f"Affected sector: {event['sector']}")
        if ss.get("count"):
            reasons.append(f"Sector activity: {ss['count']} signals; {ss['high_impact']} high-impact")
        if market.get("return_5d_pct") is not None:
            reasons.append(f"5D return: {float(market['return_5d_pct']):+.2f}%")
        if market.get("volume_vs_20d_avg") is not None:
            reasons.append(f"Volume: {float(market['volume_vs_20d_avg']):.2f}x 20D avg")
        if item.get("fundamental_score") is not None:
            reasons.append(f"Fundamentals: {float(item['fundamental_score']):.0f}/100")
        if item.get("predicted_5d") is not None:
            reasons.append(f"ML 5D: {float(item['predicted_5d']):+.2f}%")
        if opportunity.get("risk_reward") is not None:
            reasons.append(f"Estimated risk/reward: {float(opportunity['risk_reward']):.1f}x")
        return reasons[:8]

from __future__ import annotations

from datetime import datetime, timedelta
from math import sqrt

from sqlalchemy import select

from app.models.alert import OpportunityAlert
from app.models.event import MarketEvent
from app.models.fundamentals import CompanyFundamentals
from app.models.market_data import MarketData
from app.models.ml_prediction import MLPrediction
from app.models.news import NewsArticle
from app.models.stock import Stock


class RecommendationEngine:
    """Turn internal signals into a small, evidence-backed shortlist."""

    @staticmethod
    def build(db, limit: int = 5) -> list[dict]:
        alerts = db.scalars(
            select(OpportunityAlert)
            .where(OpportunityAlert.action.in_(["BUY", "WATCH"]))
            .order_by(OpportunityAlert.opportunity_score.desc(), OpportunityAlert.created_at.desc())
            .limit(60)
        ).all()
        recommendations = []
        seen = set()

        for alert in alerts:
            if alert.symbol in seen:
                continue
            seen.add(alert.symbol)
            stock = db.scalar(select(Stock).where(Stock.symbol == alert.symbol))
            if not stock:
                continue

            event = db.scalar(select(MarketEvent).where(MarketEvent.id == alert.event_id))
            news = db.scalar(select(NewsArticle).where(NewsArticle.id == event.news_id)) if event and event.news_id else None
            fundamentals = db.scalar(select(CompanyFundamentals).where(CompanyFundamentals.stock_id == stock.id))
            prediction = db.scalar(
                select(MLPrediction)
                .where(MLPrediction.stock_id == stock.id)
                .order_by(MLPrediction.prediction_time.desc())
            )

            market = RecommendationEngine._market_stats(db, stock.id)
            current_price = market.get("current_price") or (prediction.price_at_prediction if prediction else None)
            expected_5d = prediction.predicted_return_5d if prediction else None
            expected_20d = prediction.predicted_return_20d if prediction else None
            entry_low, entry_high = RecommendationEngine._entry_zone(current_price, market, alert.risk)

            fundamental_score = RecommendationEngine._fundamental_score(fundamentals)
            intelligence_score = float(alert.opportunity_score or 0)
            model_score = RecommendationEngine._model_score(prediction)
            market_score = RecommendationEngine._market_score(market)
            evidence_score = RecommendationEngine._evidence_score(db, event, news)
            composite = round(min(100, 0.40 * intelligence_score + 0.20 * fundamental_score + 0.18 * model_score + 0.12 * market_score + 0.10 * evidence_score), 1)
            priority = RecommendationEngine._priority(composite, intelligence_score, fundamental_score, model_score, evidence_score)

            recommendations.append({
                "rank": len(recommendations) + 1,
                "symbol": stock.symbol,
                "company": stock.company_name or stock.symbol,
                "sector": stock.sector or (fundamentals.sector if fundamentals else None) or (event.sector if event else None),
                "action": "BUY" if alert.action == "BUY" and composite >= 65 else "WATCH",
                "priority": priority,
                "priority_label": {"HIGH": "High priority", "MEDIUM": "Medium priority", "LOW": "Low priority"}[priority],
                "score": composite,
                "confidence": round(float(alert.confidence or 0), 3),
                "risk": alert.risk,
                "horizon": alert.expected_horizon or (event.time_horizon if event else None),
                "current_price": current_price,
                "entry_low": entry_low,
                "entry_high": entry_high,
                "predicted_5d": expected_5d,
                "predicted_20d": expected_20d,
                "model_signal": prediction.signal if prediction else None,
                "reason": alert.reason,
                "thesis": alert.title,
                "why_now": RecommendationEngine._why_now(alert, prediction, market),
                "invalidation": RecommendationEngine._invalidation(alert, prediction, market),
                "fundamentals": RecommendationEngine._fundamentals(fundamentals),
                "market": market,
                "fundamental_score": round(fundamental_score, 1),
                "model_score": round(model_score, 1),
                "market_score": round(market_score, 1),
                "evidence_score": round(evidence_score, 1),
                "evidence": {
                    "source": alert.source_name or (news.source if news else None),
                    "source_url": alert.source_url or (news.url if news else None),
                    "event_id": alert.event_id,
                    "opportunity_score": alert.opportunity_score,
                    "evidence_count": RecommendationEngine._evidence_count(db, event, news),
                },
                "news": {
                    "title": news.title if news else None,
                    "source": news.source if news else alert.source_name,
                    "source_url": news.url if news else alert.source_url,
                    "published_at": news.published_at.isoformat() if news and news.published_at else None,
                    "summary": news.summary if news else None,
                },
                "event": {
                    "title": event.title if event else alert.title,
                    "description": event.description if event else alert.reason,
                    "sector": event.sector if event else None,
                    "direction": event.direction if event else None,
                    "impact": event.impact if event else None,
                    "horizon": event.time_horizon if event else alert.expected_horizon,
                },
                "created_at": alert.created_at.isoformat(),
            })
            if len(recommendations) >= limit:
                break

        return recommendations

    @staticmethod
    def _priority(composite: float, intelligence: float, fundamentals: float, model: float, evidence: float) -> str:
        """Classify decision urgency/quality without equating it to expected return."""
        if composite >= 80 and intelligence >= 70 and fundamentals >= 60 and model >= 55 and evidence >= 55:
            return "HIGH"
        if composite >= 60 and intelligence >= 50 and (fundamentals >= 45 or model >= 50):
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _market_stats(db, stock_id: int) -> dict:
        rows = db.scalars(
            select(MarketData).where(MarketData.stock_id == stock_id).order_by(MarketData.timestamp.desc()).limit(260)
        ).all()
        rows = list(reversed(rows))
        if not rows:
            return {}
        closes = [float(r.close) for r in rows if r.close is not None]
        volumes = [float(r.volume) for r in rows if r.volume is not None and r.volume > 0]
        current = closes[-1]

        def ret(days: int):
            if len(closes) <= days or closes[-days - 1] == 0:
                return None
            return (current / closes[-days - 1] - 1) * 100

        daily_returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1]]
        recent = daily_returns[-20:]
        mean = sum(recent) / len(recent) if recent else 0
        vol20 = (sum((x - mean) ** 2 for x in recent) / len(recent)) ** 0.5 * sqrt(252) * 100 if recent else None
        high52 = max(closes[-252:])
        low52 = min(closes[-252:])
        avg20_volume = sum(volumes[-20:]) / min(20, len(volumes)) if volumes else None
        latest_volume = volumes[-1] if volumes else None
        return {
            "current_price": round(current, 2),
            "return_1d_pct": round(ret(1), 2) if ret(1) is not None else None,
            "return_5d_pct": round(ret(5), 2) if ret(5) is not None else None,
            "return_20d_pct": round(ret(20), 2) if ret(20) is not None else None,
            "return_60d_pct": round(ret(60), 2) if ret(60) is not None else None,
            "volatility_20d_annualized_pct": round(vol20, 2) if vol20 is not None else None,
            "high_52w": round(high52, 2),
            "low_52w": round(low52, 2),
            "distance_from_52w_high_pct": round((current / high52 - 1) * 100, 2) if high52 else None,
            "distance_from_52w_low_pct": round((current / low52 - 1) * 100, 2) if low52 else None,
            "volume_vs_20d_avg": round(latest_volume / avg20_volume, 2) if latest_volume and avg20_volume else None,
            "data_points": len(rows),
            "data_as_of": rows[-1].timestamp.isoformat() if rows[-1].timestamp else None,
        }

    @staticmethod
    def _market_score(m: dict) -> float:
        if not m:
            return 50.0
        score = 50.0
        r5, r20 = m.get("return_5d_pct"), m.get("return_20d_pct")
        if r5 is not None: score += max(-15, min(15, r5 * 2))
        if r20 is not None: score += max(-12, min(12, r20 * 0.8))
        volume = m.get("volume_vs_20d_avg")
        if volume is not None and volume > 1.5: score += 8
        elif volume is not None and volume < 0.7: score -= 4
        return max(0, min(100, score))

    @staticmethod
    def _evidence_count(db, event, news) -> int:
        if not event: return 1 if news else 0
        count = 1 if news else 0
        cutoff = (news.published_at - timedelta(days=7)) if news and news.published_at else datetime.utcnow() - timedelta(days=7)
        related = db.scalars(select(MarketEvent).where(MarketEvent.id != event.id, MarketEvent.event_type == event.event_type, MarketEvent.event_time >= cutoff)).all()
        return min(10, count + len(related))

    @staticmethod
    def _evidence_score(db, event, news) -> float:
        return min(100.0, 45 + RecommendationEngine._evidence_count(db, event, news) * 9)

    @staticmethod
    def _entry_zone(current, market, risk):
        if not current: return None, None
        vol = market.get("volatility_20d_annualized_pct") or 25
        discount = min(0.08, max(0.02, vol / 1000))
        if str(risk).upper() == "HIGH": discount += 0.02
        return round(current * (1 - discount), 2), round(current * (1 + min(0.01, discount / 4)), 2)

    @staticmethod
    def _fundamental_score(f) -> float:
        if not f: return 50.0
        points = 50.0
        if f.revenue_growth is not None: points += 10 if f.revenue_growth > 0.05 else (-8 if f.revenue_growth < 0 else 0)
        if f.earnings_growth is not None: points += 12 if f.earnings_growth > 0.05 else (-10 if f.earnings_growth < 0 else 0)
        if f.roe is not None: points += 10 if f.roe > 0.12 else (-5 if f.roe < 0.05 else 0)
        if f.debt_to_equity is not None: points += 8 if f.debt_to_equity < 0.8 else (-8 if f.debt_to_equity > 2 else 0)
        if f.profit_margin is not None: points += 8 if f.profit_margin > 0.08 else (-6 if f.profit_margin < 0 else 0)
        if f.pe_ratio is not None: points += 5 if 0 < f.pe_ratio < 30 else (-5 if f.pe_ratio > 60 else 0)
        return max(0.0, min(100.0, points))

    @staticmethod
    def _model_score(p) -> float:
        if not p: return 50.0
        score = 50.0
        if p.predicted_return_5d is not None: score += max(-25, min(25, float(p.predicted_return_5d) * 5))
        if p.predicted_return_20d is not None: score += max(-15, min(15, float(p.predicted_return_20d) * 3))
        if str(p.signal).upper() == "BUY": score += 10
        elif str(p.signal).upper() in {"SELL", "AVOID"}: score -= 15
        return max(0.0, min(100.0, score))

    @staticmethod
    def _fundamentals(f) -> dict:
        if not f: return {}
        return {"market_cap": f.market_cap, "revenue": f.revenue, "net_income": f.net_income, "eps": f.eps, "pe": f.pe_ratio, "pb": f.pb_ratio, "roe": f.roe, "roa": f.roa, "profit_margin": f.profit_margin, "operating_margin": f.operating_margin, "debt_to_equity": f.debt_to_equity, "revenue_growth": f.revenue_growth, "earnings_growth": f.earnings_growth, "updated_at": f.updated_at.isoformat() if f.updated_at else None}

    @staticmethod
    def _why_now(alert, prediction, market) -> str:
        parts = [f"Opportunity score {alert.opportunity_score:.0f}/100."]
        if prediction and prediction.predicted_return_5d is not None: parts.append(f"Model sees {prediction.predicted_return_5d:+.2f}% expected 5D return.")
        if market.get("return_5d_pct") is not None: parts.append(f"Stock has moved {market['return_5d_pct']:+.2f}% over 5 sessions.")
        if market.get("volume_vs_20d_avg") is not None: parts.append(f"Latest volume is {market['volume_vs_20d_avg']:.1f}x its 20-session average.")
        if alert.expected_horizon: parts.append(f"Expected horizon: {alert.expected_horizon}.")
        return " ".join(parts)

    @staticmethod
    def _invalidation(alert, prediction, market) -> str:
        if prediction and prediction.predicted_return_5d is not None and prediction.predicted_return_5d < 0: return "The quantitative signal is already weak; treat this as WATCH until the model turns positive."
        if market.get("distance_from_52w_high_pct") is not None and market["distance_from_52w_high_pct"] > -2: return "Avoid chasing if price remains within roughly 2% of its 52-week high; thesis weakens if the catalyst is fully priced in."
        return "Thesis weakens if the underlying event reverses, market reaction becomes excessive, fundamentals deteriorate, or new evidence contradicts the catalyst."

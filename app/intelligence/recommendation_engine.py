from __future__ import annotations

from sqlalchemy import select

from app.models.alert import OpportunityAlert
from app.models.event import MarketEvent
from app.models.fundamentals import CompanyFundamentals
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
            .limit(40)
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
            news = db.scalar(select(NewsArticle).where(NewsArticle.id == event.news_id)) if event else None
            fundamentals = db.scalar(select(CompanyFundamentals).where(CompanyFundamentals.stock_id == stock.id))
            prediction = db.scalar(
                select(MLPrediction)
                .where(MLPrediction.stock_id == stock.id)
                .order_by(MLPrediction.prediction_time.desc())
            )

            current_price = prediction.price_at_prediction if prediction else None
            expected_5d = prediction.predicted_return_5d if prediction else None
            expected_20d = prediction.predicted_return_20d if prediction else None
            entry_low = round(current_price * 0.98, 2) if current_price else None
            entry_high = round(current_price * 1.005, 2) if current_price else None

            fundamental_score = RecommendationEngine._fundamental_score(fundamentals)
            intelligence_score = float(alert.opportunity_score or 0)
            model_score = RecommendationEngine._model_score(prediction)
            composite = round(min(100, 0.55 * intelligence_score + 0.25 * fundamental_score + 0.20 * model_score), 1)

            recommendations.append({
                "rank": len(recommendations) + 1,
                "symbol": stock.symbol,
                "company": stock.company_name or stock.symbol,
                "sector": stock.sector or (fundamentals.sector if fundamentals else None) or (event.sector if event else None),
                "action": "BUY" if alert.action == "BUY" and composite >= 65 else "WATCH",
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
                "why_now": RecommendationEngine._why_now(alert, prediction),
                "invalidation": RecommendationEngine._invalidation(alert, prediction),
                "fundamentals": RecommendationEngine._fundamentals(fundamentals),
                "fundamental_score": round(fundamental_score, 1),
                "model_score": round(model_score, 1),
                "evidence": {
                    "source": alert.source_name or (news.source if news else None),
                    "source_url": alert.source_url or (news.url if news else None),
                    "event_id": alert.event_id,
                    "opportunity_score": alert.opportunity_score,
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
    def _fundamental_score(f) -> float:
        if not f:
            return 50.0
        points = 50.0
        if f.revenue_growth is not None:
            points += 10 if f.revenue_growth > 0.05 else (-8 if f.revenue_growth < 0 else 0)
        if f.earnings_growth is not None:
            points += 12 if f.earnings_growth > 0.05 else (-10 if f.earnings_growth < 0 else 0)
        if f.roe is not None:
            points += 10 if f.roe > 0.12 else (-5 if f.roe < 0.05 else 0)
        if f.debt_to_equity is not None:
            points += 8 if f.debt_to_equity < 0.8 else (-8 if f.debt_to_equity > 2 else 0)
        if f.profit_margin is not None:
            points += 8 if f.profit_margin > 0.08 else (-6 if f.profit_margin < 0 else 0)
        if f.pe_ratio is not None:
            points += 5 if 0 < f.pe_ratio < 30 else (-5 if f.pe_ratio > 60 else 0)
        return max(0.0, min(100.0, points))

    @staticmethod
    def _model_score(p) -> float:
        if not p:
            return 50.0
        score = 50.0
        if p.predicted_return_5d is not None:
            score += max(-25, min(25, float(p.predicted_return_5d) * 5))
        if p.predicted_return_20d is not None:
            score += max(-15, min(15, float(p.predicted_return_20d) * 3))
        if str(p.signal).upper() == "BUY":
            score += 10
        elif str(p.signal).upper() in {"SELL", "AVOID"}:
            score -= 15
        return max(0.0, min(100.0, score))

    @staticmethod
    def _fundamentals(f) -> dict:
        if not f:
            return {}
        return {
            "market_cap": f.market_cap, "revenue": f.revenue, "net_income": f.net_income,
            "eps": f.eps, "pe": f.pe_ratio, "pb": f.pb_ratio, "roe": f.roe,
            "roa": f.roa, "profit_margin": f.profit_margin, "operating_margin": f.operating_margin,
            "debt_to_equity": f.debt_to_equity, "revenue_growth": f.revenue_growth,
            "earnings_growth": f.earnings_growth,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        }

    @staticmethod
    def _why_now(alert, prediction) -> str:
        parts = [f"Opportunity score {alert.opportunity_score:.0f}/100."]
        if prediction and prediction.predicted_return_5d is not None:
            parts.append(f"Model sees {prediction.predicted_return_5d:+.2f}% expected 5D return.")
        if alert.expected_horizon:
            parts.append(f"Expected horizon: {alert.expected_horizon}.")
        return " ".join(parts)

    @staticmethod
    def _invalidation(alert, prediction) -> str:
        if prediction and prediction.predicted_return_5d is not None and prediction.predicted_return_5d < 0:
            return "The quantitative signal is already weak; treat this as WATCH until the model turns positive."
        return "Thesis weakens if the underlying event reverses, market reaction becomes excessive, or new evidence contradicts the catalyst."

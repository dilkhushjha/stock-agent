from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.market.exposures import EXPOSURE_MAP
from app.intelligence.exposure import ExposureMappingService
from app.models.event import MarketEvent
from app.models.market_data import MarketData
from app.models.news import NewsArticle
from app.models.stock import Stock


CAUSE_EFFECT = {
    "SUGAR": ("sugarcane", "sugar harvest", "sugar production", "sugar price"),
    "DEFENCE": ("defence", "defense", "military", "defence budget", "defense budget", "procurement", "missile", "navy"),
    "BANKING": ("bank", "banking", "credit", "loan", "interest rate", "repo rate", "rbi", "npa", "deposit"),
    "CRUDE OIL": ("crude", "oil price", "brent", "opec"),
    "STEEL": ("steel", "iron ore", "metal prices"),
    "RAILWAYS": ("railway", "railways", "rail budget", "wagon", "rail corridor"),
    "POWER": ("power", "electricity", "grid", "transmission", "generation", "renewable"),
    "PHARMA": ("pharma", "pharmaceutical", "drug", "medicine", "usfda", "fda"),
    "IT SERVICES": ("it services", "software", "cloud", "digital", "outsourcing"),
    "AUTO": ("auto", "automobile", "vehicle", "ev", "electric vehicle", "car sales"),
}

CHAINS = {
    "SUGAR": "Lower harvest/production -> tighter supply -> supply-demand imbalance -> realizations can rise -> producer margins may improve.",
    "DEFENCE": "Higher allocation/procurement -> larger order pipeline -> revenue visibility -> earnings expectations may improve.",
    "BANKING": "Rate/credit/liquidity change -> funding cost or credit demand changes -> margins/growth/asset quality change.",
    "CRUDE OIL": "Crude-price change -> input/fuel costs change -> sector margins change -> earnings expectations move.",
    "STEEL": "Steel/ore price change -> realizations and spreads change -> producer margins change.",
    "RAILWAYS": "Rail capex/project awards -> order pipeline grows -> execution and revenue visibility improve.",
    "POWER": "Power demand/policy/capex change -> capacity or investment changes -> utilization/order pipeline changes.",
    "PHARMA": "Regulatory/pricing/product event -> sales or compliance economics change -> margins/earnings expectations move.",
    "IT SERVICES": "Technology/client-spending change -> budgets and deal pipeline change -> revenue-growth expectations move.",
    "AUTO": "Demand/policy/commodity change -> vehicle volumes or input costs change -> margins and earnings expectations move.",
}


def clean(value):
    return " ".join(str(value or "").upper().split())


class CausalIntelligence:
    """Convert an event into cause-effect reasoning and broad-universe stock exposure."""

    @staticmethod
    def enrich_event(db: Session, event: MarketEvent | None) -> dict:
        if not event:
            return {}

        entity = ExposureMappingService.normalize_entity(event.entity or event.sector or "")
        article = db.scalar(select(NewsArticle).where(NewsArticle.id == event.news_id)) if event.news_id else None
        text = " ".join(filter(None, [event.title, event.description, article.title if article else None, article.summary if article else None])).lower()

        if entity not in CHAINS:
            for candidate, keywords in CAUSE_EFFECT.items():
                if any(k in text for k in keywords):
                    entity = candidate
                    break

        candidates = CausalIntelligence._candidate_stocks(db, event, entity)
        rows = []
        for stock, config in candidates:
            stats = CausalIntelligence._stock_event_stats(db, stock.id, event.event_date or event.created_at)
            rows.append({
                "symbol": stock.symbol,
                "company_name": stock.company_name,
                "sector": stock.sector,
                "exposure_type": "DIRECT" if config else "SECTOR",
                "exposure_strength": (config or {}).get("exposure_strength", 0.5),
                "direction": (config or {}).get("direction", event.direction or "NEUTRAL"),
                **stats,
            })

        rows.sort(key=lambda x: (-(x.get("exposure_strength") or 0), -(x.get("return_5d_pct") or -999)))

        return {
            "normalized_entity": entity,
            "sector": event.sector or entity,
            "event_type": event.event_type,
            "direction": event.direction,
            "impact": event.impact,
            "confidence": event.confidence,
            "chain": CHAINS.get(entity, "Event -> economic mechanism -> sector -> company exposure -> earnings/valuation -> market reaction."),
            "historical_reaction": CausalIntelligence._historical_reaction(db, event, entity),
            "exposed_stocks": rows[:20],
            "candidate_count": len(rows),
        }

    @staticmethod
    def _candidate_stocks(db: Session, event: MarketEvent, entity: str):
        configured = EXPOSURE_MAP.get(entity, {})
        result, seen = [], set()
        for symbol, config in configured.items():
            stock = db.scalar(select(Stock).where(Stock.symbol == symbol, Stock.is_active.is_(True)))
            if stock:
                result.append((stock, config))
                seen.add(stock.id)

        sector = clean(event.sector)
        if sector:
            stocks = db.scalars(select(Stock).where(Stock.is_active.is_(True), Stock.sector == sector)).all()
            for stock in stocks:
                if stock.id not in seen:
                    result.append((stock, None))
                    seen.add(stock.id)
        return result

    @staticmethod
    def _stock_event_stats(db: Session, stock_id: int, event_date: datetime | None) -> dict:
        if not event_date:
            return {}
        rows = db.scalars(select(MarketData).where(
            MarketData.stock_id == stock_id,
            MarketData.timestamp >= event_date - timedelta(days=3),
            MarketData.timestamp <= event_date + timedelta(days=12),
        ).order_by(MarketData.timestamp)).all()
        closes = [float(r.close) for r in rows if r.close is not None]
        if len(closes) < 2:
            return {}
        base = closes[0]
        five = closes[min(5, len(closes) - 1)]
        return {"return_5d_pct": round((five / base - 1) * 100, 2), "data_points": len(closes)}

    @staticmethod
    def _historical_reaction(db: Session, current_event: MarketEvent, entity: str) -> dict:
        event_date = current_event.event_date or current_event.created_at or datetime.utcnow()
        past = db.scalars(select(MarketEvent).where(
            MarketEvent.id != current_event.id,
            MarketEvent.event_date.is_not(None),
            MarketEvent.event_date < event_date,
            MarketEvent.event_date >= event_date - timedelta(days=730),
        ).order_by(MarketEvent.event_date.desc()).limit(100)).all()

        relevant = [e for e in past if ExposureMappingService.normalize_entity(e.entity or e.sector or "") == entity]
        returns = []
        for old_event in relevant[:30]:
            for stock, _ in CausalIntelligence._candidate_stocks(db, old_event, ExposureMappingService.normalize_entity(old_event.entity or old_event.sector or ""))[:20]:
                value = CausalIntelligence._stock_event_stats(db, stock.id, old_event.event_date).get("return_5d_pct")
                if value is not None:
                    returns.append(value)

        if not returns:
            return {"sample_count": 0, "avg_5d_return_pct": None, "median_5d_return_pct": None, "positive_outcome_rate_pct": None}
        return {
            "sample_count": len(returns),
            "avg_5d_return_pct": round(mean(returns), 2),
            "median_5d_return_pct": round(median(returns), 2),
            "positive_outcome_rate_pct": round(sum(v > 0 for v in returns) / len(returns) * 100, 1),
        }

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.market.exposures import EXPOSURE_MAP
from app.intelligence.exposure import ExposureMappingService
from app.models.event import MarketEvent
from app.models.market_data import MarketData
from app.models.news import NewsArticle
from app.models.stock import Stock


CAUSE_EFFECT = {
    "SUGAR": {
        "keywords": ("sugarcane", "sugar cane", "sugar harvest", "sugar production", "sugar price", "sugar prices"),
        "chain": "Lower sugarcane harvest / production -> tighter sugar supply -> supply-demand imbalance -> sugar prices and realizations can rise -> sugar producers' margins can improve.",
        "positive": "Producer stocks can benefit when tighter supply supports realizations and margins.",
    },
    "DEFENCE": {
        "keywords": ("defence", "defense", "military", "armed forces", "defence budget", "defense budget", "defence spending", "defense spending", "procurement", "missile", "navy", "air force"),
        "chain": "Higher defence allocation / procurement -> larger addressable order pipeline -> higher revenue/order-book visibility for exposed companies -> potential earnings and valuation support.",
        "positive": "Companies with direct government procurement exposure and strong order-book conversion are the primary beneficiaries.",
    },
    "BANKING": {
        "keywords": ("bank", "banking", "credit", "loan", "interest rate", "repo rate", "rbi", "npa", "deposit"),
        "chain": "Rate / credit / liquidity change -> funding cost and credit-demand changes -> net interest margin and loan growth change -> bank earnings expectations can move.",
        "positive": "The direction depends on whether the event improves credit growth, funding conditions, asset quality or margins.",
    },
    "CRUDE OIL": {
        "keywords": ("crude", "oil price", "oil prices", "brent", "opec"),
        "chain": "Crude-price change -> input/fuel cost changes across the economy -> margins change for producers, refiners, airlines, chemicals and transport -> sector-specific earnings expectations move.",
        "positive": "Upstream producers generally benefit from higher crude prices; downstream users can face margin pressure.",
    },
    "STEEL": {
        "keywords": ("steel", "iron ore", "metal prices", "steel prices"),
        "chain": "Steel/ore price change -> realizations and raw-material spreads change -> producer margins and earnings expectations move -> steel stocks re-rate or de-rate.",
        "positive": "Integrated producers with favorable spreads and stronger realizations are the direct beneficiaries.",
    },
    "RAILWAYS": {
        "keywords": ("railway", "railways", "rail budget", "rail budget", "wagon", "rail corridor", "rail infrastructure"),
        "chain": "Higher rail capex / project awards -> larger order pipeline -> execution and revenue visibility -> infrastructure and railway suppliers can benefit.",
        "positive": "Companies with direct order exposure and healthy execution capacity should receive the strongest read-through.",
    },
    "POWER": {
        "keywords": ("power", "electricity", "grid", "transmission", "generation", "renewable"),
        "chain": "Power-demand / policy / capex change -> generation, transmission or renewable investment changes -> order pipeline and asset utilization change -> exposed companies' earnings outlook moves.",
        "positive": "Companies directly exposed to the announced capex or capacity addition receive the strongest first-order benefit.",
    },
    "PHARMA": {
        "keywords": ("pharma", "pharmaceutical", "drug", "medicine", "usfda", "fda", "drug pricing"),
        "chain": "Regulatory / pricing / product event -> addressable sales or compliance economics change -> margins and earnings expectations change -> exposed pharma stocks react.",
        "positive": "The strongest impact belongs to companies with direct product, facility or regulatory exposure.",
    },
    "IT SERVICES": {
        "keywords": ("it services", "software", "technology", "cloud", "digital", "outsourcing"),
        "chain": "Technology / client-spending change -> enterprise technology budgets and deal pipeline change -> revenue growth expectations change -> IT-services valuations react.",
        "positive": "Companies with direct exposure to the affected geography, client vertical or technology cycle should lead the read-through.",
    },
    "AUTO": {
        "keywords": ("auto", "automobile", "vehicle", "ev", "electric vehicle", "car sales"),
        "chain": "Demand / policy / commodity change -> vehicle volumes or input costs change -> margins and earnings expectations change -> auto stocks respond.",
        "positive": "Companies with the strongest exposure to the affected vehicle segment and favorable cost structure should benefit most.",
    },
}


class CausalIntelligence:
    """Translate an event into a chronological cause-effect chain and rank exposed stocks."""

    @staticmethod
    def enrich_event(db: Session, event: MarketEvent | None) -> dict:
        if not event:
            return {}

        entity = ExposureMappingService.normalize_entity(event.entity or event.sector or "")
        article = db.scalar(select(NewsArticle).where(NewsArticle.id == event.news_id)) if event.news_id else None
        text = " ".join(filter(None, [event.title, event.description, article.title if article else None, article.summary if article else None])).lower()
        rule = CAUSE_EFFECT.get(entity)

        if not rule:
            for key, candidate in CAUSE_EFFECT.items():
                if any(keyword in text for keyword in candidate["keywords"]):
                    entity = key
                    rule = candidate
                    break

        exposures = EXPOSURE_MAP.get(entity, {})
        stock_rows = []
        for symbol, config in exposures.items():
            stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
            if not stock:
                continue
            stats = CausalIntelligence._stock_event_stats(db, stock.id, event.event_date or event.created_at)
            stock_rows.append({
                "symbol": symbol,
                "exposure_strength": config.get("exposure_strength", 0),
                "direction": config.get("direction", "NEUTRAL"),
                **stats,
            })

        stock_rows.sort(key=lambda x: (-(x.get("exposure_strength") or 0), -(x.get("return_5d_pct") or -999)))
        historical = CausalIntelligence._historical_sector_reaction(db, entity, event)

        return {
            "normalized_entity": entity,
            "event_type": event.event_type,
            "direction": event.direction,
            "impact": event.impact,
            "confidence": event.confidence,
            "chain": rule["chain"] if rule else "News/event -> economic consequence -> sector exposure -> company earnings/valuation -> market reaction.",
            "benefit_logic": rule["positive"] if rule else "Prioritize companies with direct exposure and corroborating market/fundamental evidence.",
            "historical_reaction": historical,
            "exposed_stocks": stock_rows[:8],
        }

    @staticmethod
    def _stock_event_stats(db: Session, stock_id: int, event_date: datetime | None) -> dict:
        if not event_date:
            return {}
        rows = db.scalars(
            select(MarketData)
            .where(MarketData.stock_id == stock_id, MarketData.timestamp >= event_date - timedelta(days=3), MarketData.timestamp <= event_date + timedelta(days=12))
            .order_by(MarketData.timestamp)
        ).all()
        closes = [float(row.close) for row in rows if row.close is not None]
        if len(closes) < 2:
            return {}
        base = closes[0]
        five = closes[min(5, len(closes) - 1)]
        return {"return_5d_pct": round((five / base - 1) * 100, 2), "data_points": len(closes)}

    @staticmethod
    def _historical_sector_reaction(db: Session, entity: str, current_event: MarketEvent) -> dict:
        past = db.scalars(
            select(MarketEvent)
            .where(MarketEvent.id != current_event.id, MarketEvent.event_date.is_not(None), MarketEvent.event_date < (current_event.event_date or datetime.utcnow()), MarketEvent.event_date >= (current_event.event_date or datetime.utcnow()) - timedelta(days=730))
            .order_by(MarketEvent.event_date.desc())
            .limit(30)
        ).all()
        relevant = [event for event in past if ExposureMappingService.normalize_entity(event.entity or event.sector or "") == entity]
        returns = []
        for event in relevant:
            exposures = EXPOSURE_MAP.get(entity, {})
            for symbol in exposures:
                stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
                if not stock:
                    continue
                stats = CausalIntelligence._stock_event_stats(db, stock.id, event.event_date)
                if stats.get("return_5d_pct") is not None:
                    returns.append(stats["return_5d_pct"])
        if not returns:
            return {"sample_count": 0, "avg_5d_return_pct": None, "median_5d_return_pct": None}
        ordered = sorted(returns)
        median = ordered[len(ordered) // 2]
        return {
            "sample_count": len(returns),
            "avg_5d_return_pct": round(mean(returns), 2),
            "median_5d_return_pct": round(median, 2),
            "positive_outcome_rate_pct": round(sum(1 for value in returns if value > 0) / len(returns) * 100, 1),
        }

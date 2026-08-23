from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select

from app.data.market.exposures import EXPOSURE_MAP
from app.intelligence.exposure import ExposureMappingService
from app.intelligence.event_novelty import EventNoveltyEngine
from app.intelligence.forward_return import ForwardReturnEngine
from app.intelligence.market_awareness import MarketAwarenessEngine
from app.models.event import MarketEvent
from app.models.market_data import MarketData
from app.models.stock import Stock


class OpportunityPipelineDiagnostics:
    """Explains exactly where an event stops producing an opportunity."""

    @classmethod
    def inspect_event(cls, db, event_id: int) -> dict:
        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id))
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        event_time = event.event_date or event.created_at
        entity = ExposureMappingService.normalize_entity(event.entity or "")
        group = EXPOSURE_MAP.get(entity)
        mapping = ExposureMappingService.map_event(db, event_id)

        candidates = []
        for item in mapping.get("exposures", []):
            stock = db.scalar(select(Stock).where(Stock.symbol == item["symbol"]))
            if not stock:
                candidates.append({"symbol": item["symbol"], "stock": False})
                continue

            before = db.scalar(
                select(func.count(MarketData.id)).where(
                    MarketData.stock_id == stock.id,
                    MarketData.timestamp <= event_time,
                    MarketData.timestamp >= event_time - timedelta(days=30),
                )
            ) or 0
            after = db.scalar(
                select(func.count(MarketData.id)).where(
                    MarketData.stock_id == stock.id,
                    MarketData.timestamp >= event_time,
                    MarketData.timestamp <= event_time + timedelta(days=30),
                )
            ) or 0

            forecasts = ForwardReturnEngine.forecast(db, stock, event_time)
            awareness = MarketAwarenessEngine.score(db, stock, event_time)
            candidates.append({
                "symbol": stock.symbol,
                "stock": True,
                "market_rows_before_30d": before,
                "market_rows_after_30d": after,
                "market_awareness_status": awareness.status,
                "forecast_horizons": [x.horizon_days for x in forecasts],
                "forecast_count": len(forecasts),
                "has_7d_forecast": any(x.horizon_days == 7 for x in forecasts),
            })

        novelty = EventNoveltyEngine.score(db, event)
        return {
            "event": {
                "id": event.id,
                "title": event.title,
                "event_type": event.event_type,
                "entity_raw": event.entity,
                "entity_normalized": entity,
                "event_time": event_time,
                "confidence": event.confidence,
            },
            "stages": {
                "exposure_group_exists": bool(group),
                "exposure_candidates": len(mapping.get("exposures", [])),
                "stocks_resolved": sum(1 for x in candidates if x.get("stock")),
                "novelty_available": novelty is not None,
                "opportunity_candidates": sum(1 for x in candidates if x.get("has_7d_forecast")),
            },
            "candidates": candidates,
        }

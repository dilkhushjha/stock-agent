from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.market.exposures import EXPOSURE_MAP
from app.models.event import MarketEvent
from app.models.exposure import StockExposure
from app.models.stock import Stock


class ExposureMappingService:
    @staticmethod
    def normalize_entity(entity: str) -> str:
        entity = " ".join(entity.upper().strip().split())

        aliases = {
            "SUGARCANE": "SUGAR",
            "SUGAR CANE": "SUGAR",
            "SUGARCANE HARVEST": "SUGAR",
            "SUGARCANE CROP": "SUGAR",
            "SUGAR HARVEST": "SUGAR",
            "SUGAR PRICES": "SUGAR",
            "SUGAR PRICE": "SUGAR",
            "CRUDE": "CRUDE OIL",
            "OIL": "CRUDE OIL",
            "CRUDE OIL PRICES": "CRUDE OIL",
            "STEEL PRICES": "STEEL",
            "STEEL PRICE": "STEEL",
            "INTEREST RATE": "INTEREST RATES",
            "RATES": "INTEREST RATES",
            "SPACE TECH": "SPACE",
            "SPACE TECH STOCKS": "SPACE",
            "SPACE TECHNOLOGY": "SPACE",
            "SPACE SECTOR": "SPACE",
            "SPACE INDUSTRY": "SPACE",
            "AEROSPACE": "SPACE",
        }

        if entity in aliases:
            return aliases[entity]

        # Handle LLM entities such as "Indian space tech stocks" without
        # requiring an exact string match in the exposure registry.
        if "SPACE" in entity and ("TECH" in entity or "STOCK" in entity or "SECTOR" in entity):
            return "SPACE"
        if "SUGAR" in entity:
            return "SUGAR"
        if "STEEL" in entity:
            return "STEEL"
        if "CRUDE" in entity or entity == "OIL":
            return "CRUDE OIL"

        return entity

    @staticmethod
    def map_event(db: Session, event_id: int) -> dict:
        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id))
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        entity = ExposureMappingService.normalize_entity(event.entity or "")
        exposure_group = EXPOSURE_MAP.get(entity)

        if not exposure_group:
            return {"event_id": event.id, "entity": entity, "stocks_found": 0, "exposures": []}

        exposures = []
        for symbol, config in exposure_group.items():
            stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
            if not stock:
                stock = Stock(symbol=symbol, yahoo_symbol=config["yahoo_symbol"], company_name=symbol, is_active=True)
                db.add(stock)
                db.commit()
                db.refresh(stock)

            existing = db.scalar(select(StockExposure).where(StockExposure.stock_id == stock.id, StockExposure.entity == entity))
            if not existing:
                db.add(StockExposure(
                    stock_id=stock.id,
                    entity=entity,
                    exposure_type="DIRECT",
                    exposure_strength=config["exposure_strength"],
                    direction=config["direction"],
                ))

            exposures.append({"symbol": symbol, "exposure_strength": config["exposure_strength"], "direction": config["direction"]})

        db.commit()
        return {"event_id": event.id, "entity": entity, "stocks_found": len(exposures), "exposures": exposures}

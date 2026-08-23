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
            "DEFENCE": "DEFENCE",
            "DEFENSE": "DEFENCE",
            "DEFENCE SECTOR": "DEFENCE",
            "DEFENCE STOCKS": "DEFENCE",
            "RAILWAYS": "RAILWAYS",
            "RAILWAY": "RAILWAYS",
            "RAILWAY SECTOR": "RAILWAYS",
            "POWER": "POWER",
            "ELECTRICITY": "POWER",
            "POWER SECTOR": "POWER",
            "RENEWABLE ENERGY": "RENEWABLES",
            "RENEWABLES": "RENEWABLES",
            "SOLAR": "RENEWABLES",
            "PHARMA": "PHARMA",
            "PHARMACEUTICAL": "PHARMA",
            "PHARMACEUTICALS": "PHARMA",
            "IT": "IT SERVICES",
            "IT SERVICES": "IT SERVICES",
            "INFORMATION TECHNOLOGY": "IT SERVICES",
            "AUTOMOBILE": "AUTO",
            "AUTOMOBILES": "AUTO",
            "AUTO": "AUTO",
            "EV": "AUTO",
            "FERTILIZER": "FERTILIZERS",
            "FERTILIZERS": "FERTILIZERS",
            "CEMENT": "CEMENT",
            "CEMENT SECTOR": "CEMENT",
            "BANK": "BANKING",
            "BANKS": "BANKING",
            "BANKING": "BANKING",
        }

        if entity in aliases:
            return aliases[entity]

        # Handle descriptive entities produced by the event extractor.
        if "SPACE" in entity and any(x in entity for x in ("TECH", "STOCK", "SECTOR", "INDUSTRY", "AERO")):
            return "SPACE"
        if "SUGAR" in entity:
            return "SUGAR"
        if "STEEL" in entity:
            return "STEEL"
        if "CRUDE" in entity or entity == "OIL":
            return "CRUDE OIL"
        if "DEFEN" in entity or "MILITARY" in entity:
            return "DEFENCE"
        if "RAIL" in entity:
            return "RAILWAYS"
        if "POWER" in entity or "ELECTRIC" in entity:
            return "POWER"
        if "PHARMA" in entity or "DRUG" in entity:
            return "PHARMA"
        if "FERTIL" in entity:
            return "FERTILIZERS"
        if "CEMENT" in entity:
            return "CEMENT"
        if "BANK" in entity or "LENDING" in entity or "CREDIT" in entity:
            return "BANKING"
        if "AUTO" in entity or "VEHICLE" in entity or "EV" in entity:
            return "AUTO"
        if "RENEWABLE" in entity or "SOLAR" in entity or "WIND" in entity:
            return "RENEWABLES"
        if entity in {"IT", "TECH", "SOFTWARE", "INFORMATION TECHNOLOGY"}:
            return "IT SERVICES"

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
                stock = Stock(
                    symbol=symbol,
                    yahoo_symbol=config["yahoo_symbol"],
                    company_name=config.get("company_name", symbol),
                    sector=entity,
                    is_active=True,
                )
                db.add(stock)
                db.commit()
                db.refresh(stock)
            elif not stock.sector:
                stock.sector = entity

            existing = db.scalar(
                select(StockExposure).where(
                    StockExposure.stock_id == stock.id,
                    StockExposure.entity == entity,
                )
            )
            if not existing:
                db.add(StockExposure(
                    stock_id=stock.id,
                    entity=entity,
                    exposure_type="DIRECT",
                    exposure_strength=config["exposure_strength"],
                    direction=config["direction"],
                ))

            exposures.append({
                "symbol": symbol,
                "exposure_strength": config["exposure_strength"],
                "direction": config["direction"],
            })

        db.commit()
        return {"event_id": event.id, "entity": entity, "stocks_found": len(exposures), "exposures": exposures}

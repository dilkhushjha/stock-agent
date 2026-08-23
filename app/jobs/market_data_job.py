from app.data.database import SessionLocal
from app.intelligence.market_data_sync import MarketDataSyncService


def run():
    db = SessionLocal()
    try:
        return MarketDataSyncService().sync(db)
    finally:
        db.close()

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.data.database import Base


class OpportunityAlert(Base):
    __tablename__ = "opportunity_alerts"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(
        Integer,
        ForeignKey("market_events.id"),
        nullable=False,
        index=True,
    )

    symbol = Column(String(50), nullable=False, index=True)
    factor = Column(String(100), nullable=False, index=True)
    action = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    opportunity_score = Column(Float, nullable=False)
    expected_horizon = Column(String(50), nullable=True)
    risk = Column(String(30), nullable=False, default="MEDIUM")
    title = Column(String(300), nullable=False)
    reason = Column(Text, nullable=False)
    source_url = Column(String(1000), nullable=True)
    source_name = Column(String(200), nullable=True)
    status = Column(String(30), nullable=False, default="NEW", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
)

from app.data.database import Base


class StockExposure(Base):
    __tablename__ = "stock_exposures"

    id = Column(Integer, primary_key=True, index=True)

    stock_id = Column(
        Integer,
        ForeignKey("stocks.id"),
        nullable=False,
        index=True,
    )

    entity = Column(
        String(200),
        nullable=False,
        index=True,
    )

    exposure_type = Column(
        String(50),
        nullable=False,
    )

    exposure_strength = Column(
        Float,
        nullable=False,
    )

    direction = Column(
        String(30),
        nullable=False,
    )
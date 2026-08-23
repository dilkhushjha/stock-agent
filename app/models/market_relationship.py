from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
)

from app.data.database import Base


class MarketRelationship(Base):

    __tablename__ = "market_relationships"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    source = Column(
        String(200),
        nullable=False,
        index=True,
    )

    target = Column(
        String(200),
        nullable=False,
        index=True,
    )

    relationship = Column(
        String(100),
        nullable=False,
    )

    impact = Column(
        String(30),
        nullable=False,
    )

    sensitivity = Column(
        Float,
        nullable=True,
    )

    description = Column(
        String(500),
        nullable=True,
    )
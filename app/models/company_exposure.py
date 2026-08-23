from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
)

from app.data.database import Base


class CompanyExposure(Base):

    __tablename__ = "company_exposures"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    stock_id = Column(
        Integer,
        ForeignKey("stocks.id"),
        nullable=False,
        index=True,
    )

    factor = Column(
        String(100),
        nullable=False,
        index=True,
    )

    exposure_type = Column(
        String(50),
        nullable=False,
    )

    exposure = Column(
        Float,
        nullable=False,
    )

    description = Column(
        String(500),
        nullable=True,
    )
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.data.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)

    # Canonical exchange identity.
    symbol = Column(String(30), unique=True, nullable=False, index=True)
    yahoo_symbol = Column(String(50), unique=True, nullable=False)
    exchange = Column(String(10), nullable=False, default="NSE", index=True)
    isin = Column(String(20), unique=True, nullable=True, index=True)
    series = Column(String(10), nullable=True)

    company_name = Column(String(200), nullable=True)

    # NSE Indices 4-level industry classification.
    macro_economic_sector = Column(String(100), nullable=True, index=True)
    sector = Column(String(100), nullable=True, index=True)
    industry = Column(String(150), nullable=True, index=True)
    basic_industry = Column(String(200), nullable=True, index=True)
    sector_code = Column(String(30), nullable=True)
    industry_code = Column(String(30), nullable=True)
    basic_industry_code = Column(String(40), nullable=True)
    sector_source = Column(String(50), nullable=True)
    classification_updated_at = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False, index=True)

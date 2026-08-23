from sqlalchemy import Column, Integer, String, Boolean
from app.data.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)

    symbol = Column(String(30), unique=True, nullable=False, index=True)
    yahoo_symbol = Column(String(50), unique=True, nullable=False)

    company_name = Column(String(200), nullable=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(150), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
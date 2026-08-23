from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.fundamentals_collector import (
    FundamentalsCollector,
)

from app.models.fundamentals import (
    CompanyFundamentals,
)

from app.models.stock import Stock


class FundamentalsService:

    @staticmethod
    def update_stock(
        db: Session,
        symbol: str,
    ) -> dict:

        stock = db.scalar(
            select(Stock).where(
                Stock.symbol == symbol.upper()
            )
        )

        if not stock:
            raise ValueError(
                f"Stock {symbol} not found."
            )

        if not stock.yahoo_symbol:
            raise ValueError(
                f"No Yahoo symbol configured "
                f"for {symbol}."
            )

        data = FundamentalsCollector.collect(
            stock.yahoo_symbol
        )

        fundamentals = db.scalar(
            select(CompanyFundamentals).where(
                CompanyFundamentals.stock_id
                == stock.id
            )
        )

        if not fundamentals:

            fundamentals = CompanyFundamentals(
                stock_id=stock.id
            )

            db.add(fundamentals)

        for field, value in data.items():

            setattr(
                fundamentals,
                field,
                value,
            )

        db.commit()
        db.refresh(fundamentals)

        return {
            "symbol": stock.symbol,
            "company": stock.company_name,
            "fundamentals": data,
        }
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.fundamentals_collector import FundamentalsCollector
from app.models.fundamentals import CompanyFundamentals
from app.models.stock import Stock


class FundamentalsIngestionService:
    @staticmethod
    def ingest_all(db: Session) -> dict:
        stocks = db.scalars(select(Stock).where(Stock.is_active == True)).all()
        results = {
            "total": len(stocks), "success": 0, "failed": 0,
            "sector_updated": 0, "industry_updated": 0, "financials_updated": 0,
            "failures": [],
        }

        print("\n" + "=" * 70)
        print("FUNDAMENTALS / FINANCIAL QUALITY INGESTION")
        print("=" * 70)

        for index, stock in enumerate(stocks, start=1):
            print(f"\n[{index}/{len(stocks)}] {stock.symbol}")
            try:
                db.rollback()
                data = FundamentalsCollector.collect(stock.yahoo_symbol)

                if data.get("sector"):
                    stock.sector = data["sector"]
                    results["sector_updated"] += 1
                if data.get("industry"):
                    stock.industry = data["industry"]
                    results["industry_updated"] += 1

                fundamentals = db.scalar(
                    select(CompanyFundamentals).where(CompanyFundamentals.stock_id == stock.id)
                )
                if fundamentals is None:
                    fundamentals = CompanyFundamentals(stock_id=stock.id)
                    db.add(fundamentals)

                # Persist only fields owned by the fundamentals table.
                for field in (
                    "sector", "industry", "market_cap", "pe_ratio", "pb_ratio", "revenue",
                    "net_income", "eps", "roe", "roa", "profit_margin", "operating_margin",
                    "debt_to_equity", "revenue_growth", "earnings_growth", "operating_cash_flow",
                    "capital_expenditure", "free_cash_flow", "total_debt", "cash_and_equivalents",
                    "interest_expense",
                ):
                    setattr(fundamentals, field, data.get(field))

                db.commit()
                results["success"] += 1
                results["financials_updated"] += 1
                print(f"  Sector: {data.get('sector')}")
                print(f"  Industry: {data.get('industry')}")
                print(f"  FCF: {data.get('free_cash_flow')}")
                print(f"  Operating CF: {data.get('operating_cash_flow')}")
                print(f"  Debt: {data.get('total_debt')}")

            except Exception as exc:
                db.rollback()
                results["failed"] += 1
                results["failures"].append({"symbol": stock.symbol, "error": str(exc)})
                print(f"  FAILED: {exc}")

        print("\n" + "=" * 70)
        print("FUNDAMENTALS SUMMARY")
        print("=" * 70)
        print(f"Total stocks: {results['total']}")
        print(f"Successful: {results['success']}")
        print(f"Failed: {results['failed']}")
        print(f"Financials updated: {results['financials_updated']}")
        print(f"Sectors updated: {results['sector_updated']}")
        print(f"Industries updated: {results['industry_updated']}")
        return results

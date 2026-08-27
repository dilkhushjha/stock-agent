import math

import yfinance as yf


class FundamentalsCollector:
    """Collect point-in-time company fundamentals plus financial quality inputs."""

    @staticmethod
    def _number(value):
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
        return None

    @classmethod
    def _statement_number(cls, frame, names):
        if frame is None or getattr(frame, "empty", True):
            return None
        for name in names:
            if name in frame.index:
                row = frame.loc[name]
                if hasattr(row, "iloc"):
                    for value in row.iloc[:4]:
                        value = cls._number(value)
                        if value is not None:
                            return value
                else:
                    return cls._number(row)
        return None

    @classmethod
    def collect(cls, yahoo_symbol: str) -> dict:
        ticker = yf.Ticker(yahoo_symbol)
        info = ticker.info

        def get_number(key):
            return cls._number(info.get(key))

        # yfinance statement APIs expose the latest reported fiscal periods. We use
        # the latest available value and keep the fields nullable when unavailable.
        try:
            cashflow = ticker.cashflow
        except Exception:
            cashflow = None
        try:
            balance_sheet = ticker.balance_sheet
        except Exception:
            balance_sheet = None

        operating_cash_flow = cls._statement_number(
            cashflow,
            ["Operating Cash Flow", "Total Cash From Operating Activities"],
        )
        capital_expenditure = cls._statement_number(
            cashflow,
            ["Capital Expenditure", "Capital Expenditures", "Capital Expenditure Reported"],
        )
        free_cash_flow = cls._statement_number(
            cashflow,
            ["Free Cash Flow"],
        )
        if free_cash_flow is None and operating_cash_flow is not None and capital_expenditure is not None:
            # Vendors commonly report capex as a negative cash-flow number.
            free_cash_flow = operating_cash_flow + capital_expenditure

        total_debt = get_number("totalDebt")
        cash = get_number("totalCash")
        interest_expense = get_number("interestExpense")
        if total_debt is None:
            total_debt = cls._statement_number(balance_sheet, ["Total Debt", "Long Term Debt And Capital Lease Obligation"])
        if cash is None:
            cash = cls._statement_number(balance_sheet, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"])
        if interest_expense is None:
            interest_expense = cls._statement_number(cashflow, ["Interest Paid"])

        return {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": get_number("marketCap"),
            "pe_ratio": get_number("trailingPE"),
            "pb_ratio": get_number("priceToBook"),
            "revenue": get_number("totalRevenue"),
            "net_income": get_number("netIncomeToCommon"),
            "eps": get_number("trailingEps"),
            "roe": get_number("returnOnEquity"),
            "roa": get_number("returnOnAssets"),
            "profit_margin": get_number("profitMargins"),
            "operating_margin": get_number("operatingMargins"),
            "revenue_growth": get_number("revenueGrowth"),
            "earnings_growth": get_number("earningsGrowth"),
            "debt_to_equity": get_number("debtToEquity"),
            "operating_cash_flow": operating_cash_flow,
            "capital_expenditure": capital_expenditure,
            "free_cash_flow": free_cash_flow,
            "total_debt": total_debt,
            "cash_and_equivalents": cash,
            "interest_expense": interest_expense,
        }

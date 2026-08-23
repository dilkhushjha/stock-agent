import yfinance as yf


class FundamentalsCollector:

    @staticmethod
    def collect(
        yahoo_symbol: str,
    ) -> dict:

        ticker = yf.Ticker(
            yahoo_symbol
        )

        info = ticker.info

        def get_number(key):

            value = info.get(key)

            if isinstance(
                value,
                (int, float),
            ):

                return float(value)

            return None

        return {

            # -----------------------------
            # Classification
            # -----------------------------

            "sector": info.get(
                "sector"
            ),

            "industry": info.get(
                "industry"
            ),

            # -----------------------------
            # Valuation
            # -----------------------------

            "market_cap": get_number(
                "marketCap"
            ),

            "pe_ratio": get_number(
                "trailingPE"
            ),

            "pb_ratio": get_number(
                "priceToBook"
            ),

            # -----------------------------
            # Financial performance
            # -----------------------------

            "revenue": get_number(
                "totalRevenue"
            ),

            "net_income": get_number(
                "netIncomeToCommon"
            ),

            "eps": get_number(
                "trailingEps"
            ),

            # -----------------------------
            # Profitability
            # -----------------------------

            "roe": get_number(
                "returnOnEquity"
            ),

            "roa": get_number(
                "returnOnAssets"
            ),

            "profit_margin": get_number(
                "profitMargins"
            ),

            "operating_margin": get_number(
                "operatingMargins"
            ),

            # -----------------------------
            # Growth
            # -----------------------------

            "revenue_growth": get_number(
                "revenueGrowth"
            ),

            "earnings_growth": get_number(
                "earningsGrowth"
            ),

            # -----------------------------
            # Leverage
            # -----------------------------

            "debt_to_equity": get_number(
                "debtToEquity"
            ),
        }
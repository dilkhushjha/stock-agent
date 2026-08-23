from app.collectors.fundamentals_collector import (
    FundamentalsCollector,
)


class SectorCollector:

    @staticmethod
    def collect(
        yahoo_symbol: str,
    ) -> dict:

        fundamentals = (
            FundamentalsCollector
            .collect(
                yahoo_symbol
            )
        )

        return {
            "sector": fundamentals.get(
                "sector"
            ),
            "industry": fundamentals.get(
                "industry"
            ),
        }
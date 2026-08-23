from datetime import datetime

import pandas as pd
import yfinance as yf


class MarketDataService:
    """Service responsible for retrieving market data."""

    @staticmethod
    def get_quote(symbol: str) -> dict:
        """
        Fetch the latest available quote for a stock.

        Example:
            RELIANCE.NS
            TCS.NS
            HDFCBANK.NS
        """

        ticker = yf.Ticker(symbol)

        info = ticker.fast_info

        return {
            "symbol": symbol,
            "price": info.get("last_price"),
            "previous_close": info.get(
                "previous_close"
            ),
            "day_high": info.get(
                "day_high"
            ),
            "day_low": info.get(
                "day_low"
            ),
            "volume": info.get(
                "last_volume"
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def get_history(
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Retrieve historical OHLCV data.

        Examples:

            period="1mo"
            period="1y"
            period="5y"
            period="max"

            interval="1d"
        """

        ticker = yf.Ticker(symbol)

        history = ticker.history(
            period=period,
            interval=interval,
            auto_adjust=False,
        )

        if history.empty:

            raise ValueError(
                f"No market data found for {symbol}"
            )

        history.reset_index(
            inplace=True
        )

        return history

    @staticmethod
    def get_multiple_history(
        symbols: list[str],
        period: str = "1mo",
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame]:
        """
        Retrieve historical data for multiple symbols.

        Failed symbols do not stop the entire operation.
        """

        result = {}

        for symbol in symbols:

            try:

                result[symbol] = (
                    MarketDataService
                    .get_history(
                        symbol=symbol,
                        period=period,
                        interval=interval,
                    )
                )

            except Exception as exc:

                print(
                    f"Failed to fetch "
                    f"{symbol}: {exc}"
                )

        return result
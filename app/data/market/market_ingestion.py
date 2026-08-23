from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.market.market_data import MarketDataService
from app.data.market.nifty50_universe import (
    get_nifty50_symbols,
)
from app.models.market_data import MarketData
from app.models.stock import Stock


class MarketDataIngestionService:

    @staticmethod
    def ensure_stock_exists(
        db: Session,
        symbol: str,
        yahoo_symbol: str,
    ) -> Stock:

        stock = db.scalar(
            select(Stock).where(
                Stock.symbol == symbol
            )
        )

        if stock:
            return stock

        stock = Stock(
            symbol=symbol,
            yahoo_symbol=yahoo_symbol,
            company_name=symbol,
            is_active=True,
        )

        db.add(stock)
        db.commit()
        db.refresh(stock)

        return stock

    @staticmethod
    def ingest_history(
        db: Session,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> dict:

        symbol = symbol.upper()

        # -----------------------------------------
        # Validate against the NIFTY 50 universe
        # -----------------------------------------

        universe = get_nifty50_symbols()

        if symbol not in universe:

            raise ValueError(
                f"{symbol} is not available "
                f"in the stock universe."
            )

        yahoo_symbol = universe[symbol]

        # -----------------------------------------
        # Make sure the session is clean
        # -----------------------------------------

        db.rollback()

        # -----------------------------------------
        # Ensure stock exists
        # -----------------------------------------

        stock = (
            MarketDataIngestionService
            .ensure_stock_exists(
                db=db,
                symbol=symbol,
                yahoo_symbol=yahoo_symbol,
            )
        )

        # -----------------------------------------
        # Fetch historical data
        # -----------------------------------------

        history = (
            MarketDataService
            .get_history(
                yahoo_symbol,
                period=period,
                interval=interval,
            )
        )

        inserted = 0
        skipped = 0
        invalid = 0

        # -----------------------------------------
        # Process rows
        # -----------------------------------------

        for _, row in history.iterrows():

            timestamp = row["Date"]

            if hasattr(
                timestamp,
                "to_pydatetime",
            ):
                timestamp = (
                    timestamp.to_pydatetime()
                )

            timestamp = timestamp.replace(
                tzinfo=None
            )

            # -------------------------------------
            # Validate OHLC
            # -------------------------------------

            required_values = [
                row["Open"],
                row["High"],
                row["Low"],
                row["Close"],
            ]

            if any(
                value is None
                for value in required_values
            ):

                invalid += 1
                continue

            try:

                open_price = float(
                    row["Open"]
                )

                high_price = float(
                    row["High"]
                )

                low_price = float(
                    row["Low"]
                )

                close_price = float(
                    row["Close"]
                )

            except (
                TypeError,
                ValueError,
            ):

                invalid += 1
                continue

            # pandas NaN handling

            import math

            if any(
                math.isnan(value)
                for value in [
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                ]
            ):

                invalid += 1
                continue

            # -------------------------------------
            # Check duplicate
            # -------------------------------------

            existing = db.scalar(
                select(MarketData).where(
                    MarketData.stock_id
                    == stock.id,
                    MarketData.timestamp
                    == timestamp,
                )
            )

            if existing:

                skipped += 1
                continue

            # -------------------------------------
            # Adjusted close
            # -------------------------------------

            adjusted_close = None

            if "Adj Close" in row:

                value = row["Adj Close"]

                if value is not None:

                    try:

                        value = float(value)

                        if not math.isnan(
                            value
                        ):
                            adjusted_close = value

                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

            # -------------------------------------
            # Volume
            # -------------------------------------

            volume = None

            if "Volume" in row:

                value = row["Volume"]

                if value is not None:

                    try:

                        value = float(value)

                        if not math.isnan(
                            value
                        ):
                            volume = int(value)

                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

            # -------------------------------------
            # Create record
            # -------------------------------------

            record = MarketData(
                stock_id=stock.id,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                adjusted_close=(
                    adjusted_close
                ),
                volume=volume,
            )

            db.add(record)

            inserted += 1

        # -----------------------------------------
        # Commit safely
        # -----------------------------------------

        try:

            db.commit()

        except Exception:

            db.rollback()

            raise

        return {
            "symbol": symbol,
            "records_inserted": inserted,
            "records_skipped": skipped,
            "records_invalid": invalid,
            "period": period,
            "interval": interval,
        }
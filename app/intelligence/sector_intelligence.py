import yfinance as yf

from app.intelligence.sector_config import (
    SECTOR_INDICES,
    SECTOR_PEERS,
)


class SectorIntelligence:

    @staticmethod
    def _get_ticker_data(
        symbol: str,
    ):

        try:

            ticker = yf.Ticker(symbol)

            data = ticker.history(
                period="3mo",
                interval="1d",
            )

            if data.empty:
                return None

            return data

        except Exception:

            return None

    @staticmethod
    def _calculate_metrics(
        data,
    ):

        if data is None or len(data) < 21:
            return None

        close = data["Close"]

        current = float(
            close.iloc[-1]
        )

        previous = float(
            close.iloc[-2]
        )

        price_20d = float(
            close.iloc[-21]
        )

        return_1d = (
            current / previous - 1
        ) * 100

        return_20d = (
            current / price_20d - 1
        ) * 100

        sma20 = float(
            close.tail(20).mean()
        )

        volatility = (
            close.pct_change()
            .tail(20)
            .std()
            * (252 ** 0.5)
            * 100
        )

        if (
            current > sma20
            and return_20d > 3
        ):

            trend = "BULLISH"

        elif (
            current < sma20
            and return_20d < -3
        ):

            trend = "BEARISH"

        else:

            trend = "NEUTRAL"

        return {
            "current": current,
            "return_1d": return_1d,
            "return_20d": return_20d,
            "sma20": sma20,
            "volatility": volatility,
            "trend": trend,
        }

    @staticmethod
    def _get_index_sector(
        sector: str,
    ):

        symbol = SECTOR_INDICES.get(
            sector.upper()
        )

        if not symbol:
            return None

        data = (
            SectorIntelligence
            ._get_ticker_data(symbol)
        )

        metrics = (
            SectorIntelligence
            ._calculate_metrics(data)
        )

        if not metrics:
            return None

        metrics["source"] = "INDEX"

        return metrics

    @staticmethod
    def _get_peer_sector(
        sector: str,
    ):

        peers = SECTOR_PEERS.get(
            sector.upper()
        )

        if not peers:
            return None

        returns_1d = []
        returns_20d = []
        volatilities = []

        successful = 0

        for symbol in peers:

            data = (
                SectorIntelligence
                ._get_ticker_data(symbol)
            )

            metrics = (
                SectorIntelligence
                ._calculate_metrics(data)
            )

            if not metrics:
                continue

            successful += 1

            returns_1d.append(
                metrics["return_1d"]
            )

            returns_20d.append(
                metrics["return_20d"]
            )

            volatilities.append(
                metrics["volatility"]
            )

        if successful == 0:
            return None

        avg_return_1d = (
            sum(returns_1d)
            / len(returns_1d)
        )

        avg_return_20d = (
            sum(returns_20d)
            / len(returns_20d)
        )

        avg_volatility = (
            sum(volatilities)
            / len(volatilities)
        )

        if avg_return_20d > 3:

            trend = "BULLISH"

        elif avg_return_20d < -3:

            trend = "BEARISH"

        else:

            trend = "NEUTRAL"

        bullish_count = sum(
            1
            for value in returns_20d
            if value > 0
        )

        breadth = (
            bullish_count
            / len(returns_20d)
        ) * 100

        return {
            "return_1d": avg_return_1d,
            "return_20d": avg_return_20d,
            "volatility": avg_volatility,
            "trend": trend,
            "breadth": breadth,
            "stocks_available": successful,
            "source": "PEER_BASKET",
        }

    @staticmethod
    def get_sector_data(
        sector: str,
    ) -> dict:

        sector = sector.upper()

        result = (
            SectorIntelligence
            ._get_index_sector(sector)
        )

        if result:

            return {
                "sector": sector,
                "status": "OK",
                **result,
            }

        result = (
            SectorIntelligence
            ._get_peer_sector(sector)
        )

        if result:

            return {
                "sector": sector,
                "status": "OK",
                **result,
            }

        return {
            "sector": sector,
            "status": "NO_DATA",
        }

    @staticmethod
    def get_all():

        sectors = (
            set(SECTOR_INDICES.keys())
            | set(SECTOR_PEERS.keys())
        )

        results = {}

        for sector in sorted(sectors):

            results[sector] = (
                SectorIntelligence
                .get_sector_data(sector)
            )

        return results
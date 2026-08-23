import yfinance as yf


class MarketContext:

    NIFTY = "^NSEI"
    VIX = "^INDIAVIX"

    @staticmethod
    def get_nifty_data():

        ticker = yf.Ticker(
            MarketContext.NIFTY
        )

        data = ticker.history(
            period="3mo",
            interval="1d",
        )

        if data.empty:
            return {}

        close = data["Close"]

        current = float(close.iloc[-1])

        sma20 = float(
            close.tail(20).mean()
        )

        sma50 = float(
            close.tail(50).mean()
        )

        returns_1d = (
            current / float(close.iloc[-2])
            - 1
        ) * 100

        returns_20d = (
            current / float(close.iloc[-21])
            - 1
        ) * 100

        volatility = (
            close.pct_change()
            .tail(20)
            .std()
            * (252 ** 0.5)
            * 100
        )

        return {
            "current": current,
            "sma20": sma20,
            "sma50": sma50,
            "return_1d": returns_1d,
            "return_20d": returns_20d,
            "volatility": volatility,
        }

    @staticmethod
    def get_vix():

        ticker = yf.Ticker(
            MarketContext.VIX
        )

        data = ticker.history(
            period="5d",
            interval="1d",
        )

        if data.empty:
            return None

        return float(
            data["Close"].iloc[-1]
        )

    @staticmethod
    def get():

        nifty = (
            MarketContext.get_nifty_data()
        )

        vix = MarketContext.get_vix()

        return {
            "nifty": nifty,
            "india_vix": vix,
        }
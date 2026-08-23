from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol


class MarketDataProvider(Protocol):
    def history(self, symbol: str, start: datetime, end: datetime) -> list[dict]: ...


class YahooFinanceProvider:
    """Yahoo Finance adapter with no dependency on the intelligence layer."""

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self, session=None):
        self.session = session

    def history(self, symbol: str, start: datetime, end: datetime) -> list[dict]:
        if self.session is None:
            import requests
            self.session = requests.Session()

        params = {
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
        response = self.session.get(f"{self.BASE_URL}/{symbol}", params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()["chart"]["result"][0]
        timestamps = payload.get("timestamp", [])
        quote = payload.get("indicators", {}).get("quote", [{}])[0]
        adjusted = payload.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])

        rows = []
        for index, epoch in enumerate(timestamps):
            values = {
                "open": quote.get("open", [None])[index],
                "high": quote.get("high", [None])[index],
                "low": quote.get("low", [None])[index],
                "close": quote.get("close", [None])[index],
                "volume": quote.get("volume", [None])[index],
            }
            if values["close"] is None:
                continue
            rows.append({
                "timestamp": datetime.fromtimestamp(epoch),
                **values,
                "adjusted_close": adjusted[index] if index < len(adjusted) else None,
            })
        return rows

    def recent_history(self, symbol: str, days: int = 365) -> list[dict]:
        end = datetime.utcnow()
        return self.history(symbol, end - timedelta(days=days), end)

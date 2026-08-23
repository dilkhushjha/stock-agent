from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from typing import Protocol


class MarketDataProvider(Protocol):
    def history(self, symbol: str, start: datetime, end: datetime) -> list[dict]: ...


class YahooFinanceProvider:
    """Yahoo Finance adapter with retry/backoff handling for broad-universe syncs."""

    BASE_URLS = (
        "https://query1.finance.yahoo.com/v8/finance/chart",
        "https://query2.finance.yahoo.com/v8/finance/chart",
    )

    def __init__(self, session=None, max_retries: int = 5, min_delay: float = 0.35):
        self.session = session
        self.max_retries = max(1, int(max_retries))
        self.min_delay = max(0.0, float(min_delay))
        self._last_request_at = 0.0

    def _request(self, symbol: str, params: dict):
        if self.session is None:
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "Chrome/151.0 Safari/537.36"
            })

        last_error = None
        for attempt in range(self.max_retries):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)

            base_url = self.BASE_URLS[attempt % len(self.BASE_URLS)]
            try:
                response = self.session.get(
                    f"{base_url}/{symbol}",
                    params=params,
                    timeout=30,
                )
                self._last_request_at = time.monotonic()

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        wait = float(retry_after) if retry_after else 0.0
                    except ValueError:
                        wait = 0.0
                    wait = max(wait, min(30.0, 1.5 * (2 ** attempt) + random.uniform(0.2, 1.0)))
                    time.sleep(wait)
                    last_error = RuntimeError(f"429 Too Many Requests for Yahoo Finance: {symbol}")
                    continue

                response.raise_for_status()
                return response.json()
            except Exception as exc:
                self._last_request_at = time.monotonic()
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(min(20.0, 1.2 * (2 ** attempt) + random.uniform(0.2, 0.8)))

        raise last_error or RuntimeError(f"Yahoo Finance request failed: {symbol}")

    def history(self, symbol: str, start: datetime, end: datetime) -> list[dict]:
        params = {
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
        payload = self._request(symbol, params)
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            error = (payload.get("chart") or {}).get("error")
            raise RuntimeError(f"Yahoo returned no chart data for {symbol}: {error or 'empty result'}")

        chart = result[0]
        timestamps = chart.get("timestamp", [])
        quote = chart.get("indicators", {}).get("quote", [{}])[0]
        adjusted = chart.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])

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

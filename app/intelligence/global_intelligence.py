from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class GlobalSignal:
    topic: str
    direction: str
    impact: str
    confidence: float
    horizon: str
    transmission: str
    sectors: tuple[str, ...]
    keywords: tuple[str, ...]


SIGNALS = (
    GlobalSignal("US interest rates", "BULLISH", "HIGH", .86, "MEDIUM", "rates -> USD -> foreign flows -> Indian equities", ("BANKING", "FINANCIAL SERVICES", "IT", "PHARMA"), ("fed", "federal reserve", "interest rate", "rate cut", "rate hike", "treasury yield")),
    GlobalSignal("Crude oil", "BEARISH", "HIGH", .88, "SHORT_TO_MEDIUM", "oil -> import bill -> INR/inflation -> margins", ("AVIATION", "PAINTS", "CHEMICALS", "LOGISTICS", "OIL & GAS"), ("crude", "brent", "oil price", "oil prices", "opec")),
    GlobalSignal("China demand/policy", "MIXED", "MEDIUM", .78, "MEDIUM", "China demand -> commodities/trade -> Indian exporters and inputs", ("METALS", "MINING", "CHEMICALS", "AUTO", "PHARMA"), ("china", "beijing", "chinese economy", "china stimulus", "china demand")),
    GlobalSignal("US technology cycle", "BULLISH", "MEDIUM", .76, "MEDIUM", "global technology spend -> Indian IT services demand", ("IT", "SOFTWARE", "TECHNOLOGY"), ("nvidia", "microsoft", "google", "amazon", "ai spending", "cloud spending", "technology spending")),
    GlobalSignal("Geopolitical risk", "BEARISH", "HIGH", .82, "SHORT_TO_MEDIUM", "conflict -> risk premium/commodities -> INR and market volatility", ("AVIATION", "AUTO", "CHEMICALS", "BANKING", "IT"), ("war", "conflict", "missile", "sanctions", "geopolitical", "middle east", "red sea")),
    GlobalSignal("Global metals cycle", "BULLISH", "MEDIUM", .74, "MEDIUM", "metal prices -> realizations/margins -> Indian metal producers", ("METALS", "MINING"), ("copper", "aluminium", "steel prices", "iron ore", "metal prices")),
)


def _text(article) -> str:
    return " ".join(str(getattr(article, field, "") or "") for field in ("title", "summary", "content", "source")).lower()


def detect_global_signals(articles: Iterable) -> list[dict]:
    """Classify existing news into global macro signals without pretending sentiment alone is causality."""
    found: list[dict] = []
    for article in articles:
        text = _text(article)
        for signal in SIGNALS:
            hits = sum(1 for keyword in signal.keywords if keyword in text)
            if hits == 0:
                continue
            confidence = min(.97, signal.confidence + min(.08, hits * .02))
            found.append({
                "news_id": getattr(article, "id", None),
                "title": getattr(article, "title", ""),
                "source": getattr(article, "source", None),
                "source_url": getattr(article, "url", None),
                "published_at": getattr(article, "published_at", None),
                "topic": signal.topic,
                "direction": signal.direction,
                "impact": signal.impact,
                "confidence": round(confidence, 3),
                "horizon": signal.horizon,
                "transmission": signal.transmission,
                "sectors": list(signal.sectors),
                "keyword_hits": hits,
            })
            break
    return found


def aggregate_global_impact(signals: Iterable[dict]) -> dict:
    sector_scores: dict[str, float] = {}
    topic_counts: dict[str, int] = {}
    for item in signals:
        topic_counts[item["topic"]] = topic_counts.get(item["topic"], 0) + 1
        direction = item["direction"]
        sign = 1.0 if direction == "BULLISH" else -1.0 if direction == "BEARISH" else .0
        impact = {"HIGH": 1.0, "MEDIUM": .65, "LOW": .35}.get(item["impact"], .5)
        for sector in item["sectors"]:
            sector_scores[sector] = sector_scores.get(sector, 0.0) + sign * impact * item["confidence"]
    ranked = sorted(sector_scores.items(), key=lambda x: abs(x[1]), reverse=True)
    return {"sector_impacts": [{"sector": s, "score": round(v, 2)} for s, v in ranked], "topics": topic_counts}

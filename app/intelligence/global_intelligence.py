from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class GlobalSignal:
    topic: str
    base_direction: str
    impact: str
    confidence: float
    horizon: str
    transmission: str
    sectors: tuple[str, ...]
    keywords: tuple[str, ...]
    positive_triggers: tuple[str, ...] = ()
    negative_triggers: tuple[str, ...] = ()

SIGNALS = (
    GlobalSignal("US interest rates", "MIXED", "HIGH", .86, "MEDIUM", "US rates -> USD/foreign flows -> Indian liquidity, borrowing costs and valuations", ("BANKING", "FINANCIAL SERVICES", "IT", "PHARMA"), ("fed", "federal reserve", "interest rate", "rate cut", "rate hike", "treasury yield", "fed funds"), ("rate cut", "cuts rates", "dovish", "lower yields", "yield falls"), ("rate hike", "hikes rates", "hawkish", "higher yields", "yield rises")),
    GlobalSignal("Crude oil", "MIXED", "HIGH", .88, "SHORT_TO_MEDIUM", "oil -> import bill/inflation -> INR and input costs; producer realizations move oppositely", ("AVIATION", "PAINTS", "CHEMICALS", "LOGISTICS", "OIL & GAS"), ("crude", "brent", "oil price", "oil prices", "opec", "wti"), ("oil falls", "oil prices fall", "crude falls", "oil declines", "oil drops", "lower crude"), ("oil rises", "oil prices rise", "crude rises", "oil jumps", "higher crude")),
    GlobalSignal("China demand/policy", "MIXED", "MEDIUM", .78, "MEDIUM", "China demand/policy -> commodity prices, trade and competitive pressure -> Indian sectors", ("METALS", "MINING", "CHEMICALS", "AUTO", "PHARMA"), ("china", "beijing", "chinese economy", "china stimulus", "china demand"), ("stimulus", "recovery", "demand improves", "growth accelerates", "property support"), ("slowdown", "weak demand", "property crisis", "deflation", "growth slows")),
    GlobalSignal("US technology cycle", "BULLISH", "MEDIUM", .76, "MEDIUM", "global technology/AI spending -> client technology budgets -> Indian IT services demand", ("IT", "SOFTWARE", "TECHNOLOGY"), ("nvidia", "microsoft", "google", "amazon", "ai spending", "cloud spending", "technology spending"), ("strong demand", "raises guidance", "higher capex", "increased spending", "cloud growth", "ai demand"), ("cuts guidance", "weak demand", "lower spending", "budget cuts", "technology slowdown")),
    GlobalSignal("Geopolitical risk", "BEARISH", "HIGH", .82, "SHORT_TO_MEDIUM", "conflict -> risk premium, logistics/commodity disruption -> INR, inflation and market volatility", ("AVIATION", "AUTO", "CHEMICALS", "BANKING", "IT"), ("war", "conflict", "missile", "sanctions", "geopolitical", "middle east", "red sea", "ceasefire"), ("ceasefire", "de-escalation", "peace deal", "truce"), ("war", "conflict", "missile", "sanctions", "escalation", "attack")),
    GlobalSignal("Global metals cycle", "MIXED", "MEDIUM", .74, "MEDIUM", "global metal prices -> realizations/margins -> Indian metal producers and downstream users", ("METALS", "MINING"), ("copper", "aluminium", "steel prices", "iron ore", "metal prices"), ("prices rise", "prices jump", "prices surge", "demand improves", "supply tightens"), ("prices fall", "prices drop", "prices plunge", "demand weakens", "oversupply")),
)

NEGATION = ("no ", "not ", "without ", "unlikely ")

# The signals above tag sectors using market-desk shorthand (BANKING, IT, OIL & GAS).
# Stocks in this app are classified with yfinance's GICS-style sector field
# (e.g. "Financial Services", "Technology", "Energy"). Without this alias map,
# a stock's sector would never match a signal's sector tag and every global
# score would silently fall back to neutral.
SECTOR_ALIASES: dict[str, tuple[str, ...]] = {
    "FINANCIAL SERVICES": ("BANKING", "FINANCIAL SERVICES"),
    "TECHNOLOGY": ("IT", "SOFTWARE", "TECHNOLOGY"),
    "HEALTHCARE": ("PHARMA",),
    "BASIC MATERIALS": ("METALS", "MINING", "CHEMICALS"),
    "CONSUMER CYCLICAL": ("AUTO",),
    "ENERGY": ("OIL & GAS",),
    "INDUSTRIALS": ("AVIATION", "LOGISTICS"),
}


def sector_tags_for(yahoo_sector: str | None) -> tuple[str, ...]:
    """Map a stock's yfinance sector to the signal-sector tags it should match."""
    if not yahoo_sector:
        return ()
    key = yahoo_sector.strip().upper()
    return SECTOR_ALIASES.get(key, (key,))

def _text(article) -> str:
    return " ".join(str(getattr(article, field, "") or "") for field in ("title", "summary", "content", "source")).lower()

def _direction(signal: GlobalSignal, text: str):
    positive = [x for x in signal.positive_triggers if x in text]
    negative = [x for x in signal.negative_triggers if x in text]
    if positive and not negative: direction = "BULLISH"
    elif negative and not positive: direction = "BEARISH"
    elif positive and negative: direction = "MIXED"
    else: direction = signal.base_direction
    confidence = min(.97, signal.confidence + (.04 if positive or negative else 0.0))
    return direction, confidence, positive, negative

def detect_global_signals(articles: Iterable) -> list[dict]:
    found = []
    for article in articles:
        text = _text(article)
        for signal in SIGNALS:
            hits = [k for k in signal.keywords if k in text]
            if not hits: continue
            direction, confidence, positive, negative = _direction(signal, text)
            if any(f"{neg}{trigger}" in text for neg in NEGATION for trigger in hits): confidence = max(.45, confidence - .08)
            found.append({"news_id": getattr(article, "id", None), "title": getattr(article, "title", ""), "source": getattr(article, "source", None), "source_url": getattr(article, "url", None), "published_at": getattr(article, "published_at", None), "topic": signal.topic, "direction": direction, "impact": signal.impact, "confidence": round(confidence, 3), "horizon": signal.horizon, "transmission": signal.transmission, "sectors": list(signal.sectors), "keyword_hits": hits, "directional_positive_hits": positive, "directional_negative_hits": negative})
            break
    return found

def aggregate_global_impact(signals: Iterable[dict]) -> dict:
    sector_scores, sector_evidence, topic_counts = {}, {}, {}
    for item in signals:
        topic = item["topic"]; topic_counts[topic] = topic_counts.get(topic, 0) + 1
        direction = str(item.get("direction") or "MIXED").upper()
        sign = 1.0 if direction == "BULLISH" else -1.0 if direction == "BEARISH" else 0.0
        impact = {"CRITICAL": 1.0, "SEVERE": .95, "HIGH": 1.0, "MEDIUM": .65, "LOW": .35}.get(str(item.get("impact") or "").upper(), .5)
        contribution = sign * impact * float(item.get("confidence") or .5)
        for sector in item.get("sectors", []):
            sector_scores[sector] = sector_scores.get(sector, 0.0) + contribution
            sector_evidence[sector] = sector_evidence.get(sector, 0) + 1
    ranked = sorted(sector_scores.items(), key=lambda x: abs(x[1]), reverse=True)
    return {"sector_impacts": [{"sector": s, "score": round(v, 2), "signals": sector_evidence.get(s, 0)} for s, v in ranked], "topics": topic_counts}

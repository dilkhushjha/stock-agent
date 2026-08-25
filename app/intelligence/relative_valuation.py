from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class RelativeValuation:
    score: float
    sector: str | None
    peer_count: int
    pe: float | None
    peer_pe_median: float | None
    pe_premium_pct: float | None
    pb: float | None
    peer_pb_median: float | None
    pb_premium_pct: float | None
    earnings_growth: float | None
    valuation_status: str
    flags: list[str]

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 1), "sector": self.sector, "peer_count": self.peer_count,
            "pe": self.pe, "peer_pe_median": self.peer_pe_median,
            "pe_premium_pct": None if self.pe_premium_pct is None else round(self.pe_premium_pct, 1),
            "pb": self.pb, "peer_pb_median": self.peer_pb_median,
            "pb_premium_pct": None if self.pb_premium_pct is None else round(self.pb_premium_pct, 1),
            "earnings_growth": self.earnings_growth, "valuation_status": self.valuation_status,
            "flags": self.flags,
        }


class RelativeValuationEngine:
    """Compare valuation with sector peers using robust median benchmarks."""

    @staticmethod
    def assess(stock, fundamentals, peers: list) -> RelativeValuation:
        sector = getattr(stock, "sector", None) or getattr(fundamentals, "sector", None)
        sector = str(sector).strip() if sector else None
        pe = _positive(getattr(fundamentals, "pe_ratio", None))
        pb = _positive(getattr(fundamentals, "pb_ratio", None))
        growth = _number(getattr(fundamentals, "earnings_growth", None))

        peer_pes, peer_pbs = [], []
        for peer in peers:
            if getattr(peer, "stock_id", None) == getattr(fundamentals, "stock_id", None):
                continue
            p, b = _positive(getattr(peer, "pe_ratio", None)), _positive(getattr(peer, "pb_ratio", None))
            if p is not None and p <= 150: peer_pes.append(p)
            if b is not None and b <= 30: peer_pbs.append(b)

        peer_pe = median(peer_pes) if len(peer_pes) >= 2 else None
        peer_pb = median(peer_pbs) if len(peer_pbs) >= 2 else None
        pe_premium = ((pe / peer_pe) - 1) * 100 if pe is not None and peer_pe else None
        pb_premium = ((pb / peer_pb) - 1) * 100 if pb is not None and peer_pb else None

        score, flags = 50.0, []
        if pe_premium is not None:
            score += _relative_multiple_score(pe_premium)
            if pe_premium >= 40: flags.append("P/E is materially above the sector median")
            elif pe_premium <= -25: flags.append("P/E is materially below the sector median")
        if pb_premium is not None:
            score += _relative_multiple_score(pb_premium) * 0.55
            if pb_premium >= 50: flags.append("P/B is materially above the sector median")

        if pe_premium is not None and growth is not None:
            if pe_premium >= 25 and growth >= 0.20:
                score += 7; flags.append("Premium P/E has strong earnings-growth support")
            elif pe_premium >= 25 and growth < 0.10:
                score -= 8; flags.append("Premium P/E has weak earnings-growth support")

        peer_count = max(len(peer_pes), len(peer_pbs))
        if peer_count < 2:
            score = min(score, 60.0)
            flags.append("Insufficient sector peers for reliable relative valuation")

        score = max(0.0, min(100.0, score))
        status = "ATTRACTIVE" if score >= 68 else "FAIR" if score >= 48 else "EXPENSIVE"
        return RelativeValuation(score, sector, peer_count, pe, peer_pe, pe_premium, pb, peer_pb, pb_premium, growth, status, flags[:6])


def _number(value):
    try: return float(value) if value is not None else None
    except (TypeError, ValueError): return None


def _positive(value):
    value = _number(value)
    return value if value is not None and value > 0 else None


def _relative_multiple_score(premium_pct: float) -> float:
    return max(-20.0, min(20.0, -premium_pct * 0.30))

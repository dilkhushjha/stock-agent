from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FundamentalAssessment:
    score: float
    quality_score: float
    growth_score: float
    balance_sheet_score: float
    profitability_score: float
    valuation_score: float
    completeness: float
    classification: str
    flags: list[str]

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "quality_score": round(self.quality_score, 1),
            "growth_score": round(self.growth_score, 1),
            "balance_sheet_score": round(self.balance_sheet_score, 1),
            "profitability_score": round(self.profitability_score, 1),
            "valuation_score": round(self.valuation_score, 1),
            "data_completeness": round(self.completeness, 2),
            "classification": self.classification,
            "flags": self.flags,
        }


class FundamentalIntelligence:
    """Evidence-based fundamental assessment using the fields currently stored by StockAgent.

    The score deliberately separates company quality from valuation. Missing data is not
    treated as a positive signal, and a high-quality company can still be penalised for
    an extreme valuation.
    """

    @staticmethod
    def assess(f) -> FundamentalAssessment:
        if f is None:
            return FundamentalAssessment(35, 35, 35, 35, 35, 35, 0, "INSUFFICIENT_DATA", ["No fundamentals available"])

        values = {
            "revenue": getattr(f, "revenue", None),
            "net_income": getattr(f, "net_income", None),
            "eps": getattr(f, "eps", None),
            "pe": getattr(f, "pe_ratio", None),
            "pb": getattr(f, "pb_ratio", None),
            "roe": getattr(f, "roe", None),
            "roa": getattr(f, "roa", None),
            "margin": getattr(f, "profit_margin", None),
            "op_margin": getattr(f, "operating_margin", None),
            "rev_growth": getattr(f, "revenue_growth", None),
            "earn_growth": getattr(f, "earnings_growth", None),
            "debt_equity": getattr(f, "debt_to_equity", None),
        }
        present = sum(v is not None for v in values.values())
        completeness = present / len(values)
        flags: list[str] = []

        # Growth: reward durable positive growth, strongly penalise contraction.
        growth = 50.0
        growth += FundamentalIntelligence._growth(values["rev_growth"], 14)
        growth += FundamentalIntelligence._growth(values["earn_growth"], 16)
        if values["rev_growth"] is not None and values["earn_growth"] is not None:
            if values["rev_growth"] > 0 and values["earn_growth"] > values["rev_growth"]:
                growth += 6
                flags.append("Earnings growth is outpacing revenue growth")
            elif values["rev_growth"] > 0 and values["earn_growth"] < 0:
                flags.append("Earnings are contracting despite revenue growth")
        growth = _clamp(growth)

        # Profitability: combine returns, margins and operating efficiency.
        profitability = 45.0
        profitability += FundamentalIntelligence._roe(values["roe"])
        profitability += FundamentalIntelligence._roa(values["roa"])
        profitability += FundamentalIntelligence._margin(values["margin"], 10)
        profitability += FundamentalIntelligence._margin(values["op_margin"], 8)
        profitability = _clamp(profitability)

        # Balance sheet: debt is the only leverage field currently persisted.
        balance = 55.0
        debt = values["debt_equity"]
        if debt is None:
            flags.append("Debt/equity unavailable")
        elif debt < 0:
            balance -= 15
            flags.append("Debt/equity data is abnormal")
        elif debt <= 0.25:
            balance += 25
            flags.append("Very low leverage")
        elif debt <= 0.75:
            balance += 16
        elif debt <= 1.5:
            balance += 4
        elif debt <= 2.5:
            balance -= 14
            flags.append("Elevated leverage")
        else:
            balance -= 30
            flags.append("High leverage")
        balance = _clamp(balance)

        # Quality is not simply profitability: consistency proxies are growth + returns + leverage.
        quality = _clamp(0.40 * profitability + 0.35 * growth + 0.25 * balance)

        # Valuation is deliberately conservative. Cheap is not automatically good and expensive
        # is not automatically bad; extreme multiples are penalised while moderate multiples score.
        valuation = 50.0
        pe = values["pe"]
        pb = values["pb"]
        if pe is None:
            flags.append("P/E unavailable")
        elif pe <= 0:
            valuation -= 20
            flags.append("P/E is non-positive")
        elif pe <= 12:
            valuation += 24
        elif pe <= 20:
            valuation += 16
        elif pe <= 30:
            valuation += 7
        elif pe <= 45:
            valuation -= 4
        elif pe <= 70:
            valuation -= 18
            flags.append("High P/E")
        else:
            valuation -= 30
            flags.append("Extreme P/E")

        if pb is not None:
            if pb <= 1.5:
                valuation += 12
            elif pb <= 3:
                valuation += 7
            elif pb <= 6:
                valuation -= 2
            elif pb <= 10:
                valuation -= 12
            else:
                valuation -= 20
                flags.append("High P/B")

        # Growth can justify some valuation premium; weak growth cannot.
        if pe is not None and pe > 35 and (values["earn_growth"] is None or values["earn_growth"] < 0.10):
            valuation -= 10
            flags.append("Valuation looks demanding relative to earnings growth")
        if pe is not None and pe > 45 and values["earn_growth"] is not None and values["earn_growth"] > 0.25:
            valuation += 6

        valuation = _clamp(valuation)

        # Overall score: quality dominates, valuation prevents paying any price.
        score = _clamp(0.34 * quality + 0.22 * growth + 0.18 * profitability + 0.14 * balance + 0.12 * valuation)
        if completeness < 0.50:
            score = min(score, 58.0)
            flags.append("Fundamental coverage is incomplete")
        elif completeness < 0.75:
            score = min(score, 72.0)
            flags.append("Fundamental coverage is partial")

        classification = (
            "EXCELLENT" if score >= 82 else
            "STRONG" if score >= 70 else
            "HEALTHY" if score >= 58 else
            "MIXED" if score >= 45 else
            "WEAK"
        )

        return FundamentalAssessment(
            score=score,
            quality_score=quality,
            growth_score=growth,
            balance_sheet_score=balance,
            profitability_score=profitability,
            valuation_score=valuation,
            completeness=completeness,
            classification=classification,
            flags=flags[:8],
        )

    @staticmethod
    def _growth(value, weight):
        if value is None:
            return 0.0
        if value >= 0.30:
            return weight
        if value >= 0.15:
            return weight * 0.75
        if value >= 0.05:
            return weight * 0.40
        if value >= 0:
            return 0.0
        if value >= -0.10:
            return -weight * 0.45
        return -weight

    @staticmethod
    def _roe(value):
        if value is None:
            return 0.0
        return 12 if value >= 0.20 else 8 if value >= 0.15 else 3 if value >= 0.10 else -5 if value < 0.05 else 0

    @staticmethod
    def _roa(value):
        if value is None:
            return 0.0
        return 7 if value >= 0.10 else 4 if value >= 0.06 else 1 if value >= 0.03 else -5 if value < 0 else 0

    @staticmethod
    def _margin(value, weight):
        if value is None:
            return 0.0
        if value >= 0.25:
            return weight
        if value >= 0.15:
            return weight * 0.75
        if value >= 0.08:
            return weight * 0.40
        if value >= 0:
            return 0.0
        return -weight


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))

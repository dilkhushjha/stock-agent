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
    cash_flow_score: float
    earnings_quality_score: float
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
            "cash_flow_score": round(self.cash_flow_score, 1),
            "earnings_quality_score": round(self.earnings_quality_score, 1),
            "data_completeness": round(self.completeness, 2),
            "classification": self.classification,
            "flags": self.flags,
        }


class FundamentalIntelligence:
    """Fundamental assessment using profitability, growth, leverage, cash generation and valuation."""

    @staticmethod
    def assess(f) -> FundamentalAssessment:
        if f is None:
            return FundamentalAssessment(35, 35, 35, 35, 35, 35, 35, 35, 0, "INSUFFICIENT_DATA", ["No fundamentals available"])

        values = {
            "revenue": getattr(f, "revenue", None), "net_income": getattr(f, "net_income", None),
            "eps": getattr(f, "eps", None), "pe": getattr(f, "pe_ratio", None), "pb": getattr(f, "pb_ratio", None),
            "roe": getattr(f, "roe", None), "roa": getattr(f, "roa", None), "margin": getattr(f, "profit_margin", None),
            "op_margin": getattr(f, "operating_margin", None), "rev_growth": getattr(f, "revenue_growth", None),
            "earn_growth": getattr(f, "earnings_growth", None), "debt_equity": getattr(f, "debt_to_equity", None),
            "ocf": getattr(f, "operating_cash_flow", None), "capex": getattr(f, "capital_expenditure", None),
            "fcf": getattr(f, "free_cash_flow", None), "debt": getattr(f, "total_debt", None),
            "cash": getattr(f, "cash_and_equivalents", None), "interest": getattr(f, "interest_expense", None),
        }
        present = sum(v is not None for v in values.values())
        completeness = present / len(values)
        flags: list[str] = []

        growth = 50.0 + FundamentalIntelligence._growth(values["rev_growth"], 14) + FundamentalIntelligence._growth(values["earn_growth"], 16)
        if values["rev_growth"] is not None and values["earn_growth"] is not None:
            if values["rev_growth"] > 0 and values["earn_growth"] > values["rev_growth"]:
                growth += 6; flags.append("Earnings growth is outpacing revenue growth")
            elif values["rev_growth"] > 0 and values["earn_growth"] < 0:
                flags.append("Earnings are contracting despite revenue growth")
        growth = _clamp(growth)

        profitability = 45.0 + FundamentalIntelligence._roe(values["roe"]) + FundamentalIntelligence._roa(values["roa"])
        profitability += FundamentalIntelligence._margin(values["margin"], 10) + FundamentalIntelligence._margin(values["op_margin"], 8)
        profitability = _clamp(profitability)

        balance = 55.0
        debt_eq = values["debt_equity"]
        if debt_eq is None:
            flags.append("Debt/equity unavailable")
        elif debt_eq < 0:
            balance -= 15; flags.append("Debt/equity data is abnormal")
        elif debt_eq <= 0.25: balance += 25; flags.append("Very low leverage")
        elif debt_eq <= 0.75: balance += 16
        elif debt_eq <= 1.5: balance += 4
        elif debt_eq <= 2.5: balance -= 14; flags.append("Elevated leverage")
        else: balance -= 30; flags.append("High leverage")

        debt, cash, interest = values["debt"], values["cash"], values["interest"]
        if debt is not None and cash is not None:
            net_debt = debt - cash
            if net_debt < 0: balance += 8; flags.append("Cash exceeds reported debt")
            elif debt > 0 and net_debt / debt > 0.75: balance -= 8; flags.append("Limited cash offset to debt")
        if interest is not None and values["ocf"] is not None and interest > 0:
            coverage = values["ocf"] / interest
            if coverage >= 8: balance += 7
            elif coverage < 2: balance -= 10; flags.append("Weak operating-cash-flow interest coverage")
        balance = _clamp(balance)

        cash_flow = 50.0
        ocf, fcf, revenue, net_income = values["ocf"], values["fcf"], values["revenue"], values["net_income"]
        if ocf is None: flags.append("Operating cash flow unavailable")
        else:
            if revenue and revenue > 0:
                ocf_margin = ocf / revenue
                cash_flow += _ratio_score(ocf_margin, 0.03, 0.15, 18)
            if ocf < 0: cash_flow -= 20; flags.append("Operating cash flow is negative")
        if fcf is None: flags.append("Free cash flow unavailable")
        else:
            if revenue and revenue > 0: cash_flow += _ratio_score(fcf / revenue, 0.02, 0.12, 16)
            if fcf < 0: cash_flow -= 18; flags.append("Free cash flow is negative")
        if fcf is not None and net_income is not None and net_income > 0:
            conversion = fcf / net_income
            if conversion >= 1.0: cash_flow += 10
            elif conversion >= 0.70: cash_flow += 5
            elif conversion < 0.40: cash_flow -= 8; flags.append("Free-cash-flow conversion is weak")
        cash_flow = _clamp(cash_flow)

        # Earnings quality checks whether reported profit is supported by cash generation.
        earnings_quality = 50.0
        if ocf is not None and net_income is not None and net_income > 0:
            conversion = ocf / net_income
            if conversion >= 1.0: earnings_quality += 22; flags.append("Operating cash flow fully supports reported profit")
            elif conversion >= 0.70: earnings_quality += 12
            elif conversion < 0.40: earnings_quality -= 18; flags.append("Reported profit has weak operating-cash-flow support")
        if values["margin"] is not None and values["op_margin"] is not None:
            if values["margin"] > values["op_margin"] + 0.08:
                earnings_quality -= 8; flags.append("Net margin is unusually above operating margin")
        if values["eps"] is not None and values["earn_growth"] is not None and values["earn_growth"] < -0.15:
            earnings_quality -= 8; flags.append("EPS growth is materially negative")
        earnings_quality = _clamp(earnings_quality)

        quality = _clamp(0.28 * profitability + 0.25 * growth + 0.20 * cash_flow + 0.15 * earnings_quality + 0.12 * balance)

        valuation = 50.0
        pe, pb = values["pe"], values["pb"]
        if pe is None: flags.append("P/E unavailable")
        elif pe <= 0: valuation -= 20; flags.append("P/E is non-positive")
        elif pe <= 12: valuation += 24
        elif pe <= 20: valuation += 16
        elif pe <= 30: valuation += 7
        elif pe <= 45: valuation -= 4
        elif pe <= 70: valuation -= 18; flags.append("High P/E")
        else: valuation -= 30; flags.append("Extreme P/E")
        if pb is not None:
            if pb <= 1.5: valuation += 12
            elif pb <= 3: valuation += 7
            elif pb <= 6: valuation -= 2
            elif pb <= 10: valuation -= 12
            else: valuation -= 20; flags.append("High P/B")
        if pe is not None and pe > 35 and (values["earn_growth"] is None or values["earn_growth"] < 0.10):
            valuation -= 10; flags.append("Valuation looks demanding relative to earnings growth")
        if pe is not None and pe > 45 and values["earn_growth"] is not None and values["earn_growth"] > 0.25:
            valuation += 6
        valuation = _clamp(valuation)

        score = _clamp(0.30 * quality + 0.18 * growth + 0.14 * profitability + 0.12 * balance + 0.10 * cash_flow + 0.08 * earnings_quality + 0.08 * valuation)
        if completeness < 0.50:
            score = min(score, 58.0); flags.append("Fundamental coverage is incomplete")
        elif completeness < 0.75:
            score = min(score, 72.0); flags.append("Fundamental coverage is partial")

        classification = "EXCELLENT" if score >= 82 else "STRONG" if score >= 70 else "HEALTHY" if score >= 58 else "MIXED" if score >= 45 else "WEAK"
        return FundamentalAssessment(score, quality, growth, balance, profitability, valuation, cash_flow, earnings_quality, completeness, classification, flags[:10])

    @staticmethod
    def _growth(value, weight):
        if value is None: return 0.0
        if value >= 0.30: return weight
        if value >= 0.15: return weight * 0.75
        if value >= 0.05: return weight * 0.40
        if value >= 0: return 0.0
        if value >= -0.10: return -weight * 0.45
        return -weight

    @staticmethod
    def _roe(value):
        if value is None: return 0
        return 12 if value >= 0.20 else 8 if value >= 0.15 else 3 if value >= 0.10 else -5 if value < 0.05 else 0

    @staticmethod
    def _roa(value):
        if value is None: return 0
        return 7 if value >= 0.10 else 4 if value >= 0.06 else 1 if value >= 0.03 else -5 if value < 0 else 0

    @staticmethod
    def _margin(value, weight):
        if value is None: return 0
        if value >= 0.25: return weight
        if value >= 0.15: return weight * 0.75
        if value >= 0.08: return weight * 0.40
        if value >= 0: return 0
        return -weight


def _ratio_score(value, low, high, weight):
    if value <= 0: return -weight
    if value >= high: return weight
    if value <= low: return 0
    return weight * (value - low) / (high - low)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))

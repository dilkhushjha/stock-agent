from types import SimpleNamespace

from app.intelligence.fundamental_intelligence import FundamentalIntelligence


def make(**overrides):
    values = dict(
        revenue=1000,
        net_income=150,
        eps=10,
        pe_ratio=18,
        pb_ratio=2.2,
        roe=0.18,
        roa=0.08,
        profit_margin=0.15,
        operating_margin=0.20,
        revenue_growth=0.12,
        earnings_growth=0.18,
        debt_to_equity=0.45,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_strong_company_scores_well():
    assessment = FundamentalIntelligence.assess(make())
    assert assessment.score >= 70
    assert assessment.classification in {"STRONG", "EXCELLENT"}
    assert assessment.completeness == 1.0


def test_high_leverage_and_contraction_are_penalized():
    assessment = FundamentalIntelligence.assess(
        make(debt_to_equity=3.5, revenue_growth=-0.15, earnings_growth=-0.25, pe_ratio=80)
    )
    assert assessment.score < 50
    assert "High leverage" in assessment.flags
    assert "Extreme P/E" in assessment.flags


def test_missing_data_reduces_confidence_in_score():
    assessment = FundamentalIntelligence.assess(
        make(roe=None, roa=None, pb_ratio=None, debt_to_equity=None, operating_margin=None)
    )
    assert assessment.completeness < 0.75
    assert "Fundamental coverage is partial" in assessment.flags


def test_expensive_stock_with_fast_growth_is_not_automatically_rejected():
    assessment = FundamentalIntelligence.assess(
        make(pe_ratio=48, earnings_growth=0.40, revenue_growth=0.30, roe=0.25)
    )
    assert assessment.valuation_score > 40
    assert assessment.growth_score >= 75

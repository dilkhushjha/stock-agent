from types import SimpleNamespace

from app.intelligence.relative_valuation import RelativeValuationEngine


def f(stock_id, pe, pb, growth):
    return SimpleNamespace(stock_id=stock_id, pe_ratio=pe, pb_ratio=pb, earnings_growth=growth, sector="BANKS")


def test_discounted_stock_scores_better_than_peer():
    stock = SimpleNamespace(id=1, sector="BANKS")
    target = f(1, 12, 1.6, 0.14)
    peers = [target, f(2, 20, 2.4, 0.10), f(3, 22, 2.6, 0.08), f(4, 24, 2.8, 0.06)]
    result = RelativeValuationEngine.assess(stock, target, peers)
    assert result.peer_pe_median == 22
    assert result.pe_premium_pct < 0
    assert result.score > 50
    assert result.valuation_status == "ATTRACTIVE"


def test_expensive_multiple_without_growth_is_penalized():
    stock = SimpleNamespace(id=1, sector="BANKS")
    target = f(1, 40, 5, 0.06)
    peers = [target, f(2, 20, 2, 0.15), f(3, 22, 2.2, 0.12), f(4, 18, 1.8, 0.10)]
    result = RelativeValuationEngine.assess(stock, target, peers)
    assert result.pe_premium_pct > 50
    assert result.score < 50
    assert any("weak earnings-growth support" in flag for flag in result.flags)


def test_insufficient_peers_does_not_claim_strong_relative_value():
    stock = SimpleNamespace(id=1, sector="BANKS")
    target = f(1, 10, 1, 0.20)
    result = RelativeValuationEngine.assess(stock, target, [target])
    assert result.peer_count == 0
    assert result.score <= 60
    assert result.valuation_status in {"FAIR", "EXPENSIVE"}

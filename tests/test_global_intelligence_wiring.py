from app.intelligence.global_intelligence import sector_tags_for
from app.intelligence.recommendation_engine import RecommendationEngine


def test_sector_tags_map_yfinance_sectors_to_signal_tags():
    # Without this alias map, a stock's yfinance sector would never match a
    # global-intelligence signal tag (e.g. "Financial Services" vs "BANKING"),
    # and every global score would silently be neutral.
    assert "BANKING" in sector_tags_for("Financial Services")
    assert "IT" in sector_tags_for("Technology")
    assert "OIL & GAS" in sector_tags_for("Energy")


def test_unmapped_sector_falls_back_to_uppercased_input():
    assert sector_tags_for("Real Estate") == ("REAL ESTATE",)


def test_global_assessment_is_neutral_with_no_signals():
    result = RecommendationEngine._global_assessment({}, "Technology")
    assert result["score"] == 50.0
    assert result["matched"] is False


def test_global_assessment_is_neutral_when_sector_missing():
    global_impacts = {"IT": {"sector": "IT", "score": 20.0, "signals": 40}}
    result = RecommendationEngine._global_assessment(global_impacts, None)
    assert result["score"] == 50.0
    assert result["matched"] is False


def test_global_assessment_normalizes_by_signal_count_not_raw_sum():
    # A sector mentioned in many articles must not blow past the 0-100 scale;
    # the score should reflect average conviction per signal, not total volume.
    global_impacts = {"IT": {"sector": "IT", "score": 26.18, "signals": 55}}
    result = RecommendationEngine._global_assessment(global_impacts, "Technology")
    assert 0.0 <= result["score"] <= 100.0
    assert result["score"] > 50.0  # positive average impact should push above neutral
    assert result["matched"] is True
    assert result["matched_sector_tag"] == "IT"


def test_global_assessment_picks_strongest_matching_tag():
    global_impacts = {
        "BANKING": {"sector": "BANKING", "score": 1.0, "signals": 2},
        "FINANCIAL SERVICES": {"sector": "FINANCIAL SERVICES", "score": 8.0, "signals": 10},
    }
    result = RecommendationEngine._global_assessment(global_impacts, "Financial Services")
    assert result["matched_sector_tag"] == "FINANCIAL SERVICES"

from app.intelligence.opportunity_engine import OpportunityEngine


def test_policy_event_weights_intelligence_over_market():
    item = {
        "intelligence_score": 85,
        "fundamental_score": 65,
        "model_score": 55,
        "market_score": 60,
        "evidence_score": 70,
        "predicted_5d": 4.0,
        "predicted_20d": 8.0,
        "market": {"volatility_20d_annualized_pct": 25},
        "risk": "MEDIUM",
        "event": {"event_type": "government_policy", "impact": "HIGH"},
    }

    result = OpportunityEngine.score(item)

    assert result["weight_profile"].startswith("Government Policy")
    assert result["weights"]["intelligence"] > result["weights"]["market"]
    assert result["score"] > 0
    assert result["estimated_target_probability_20d_pct"] > 0
    assert result["risk_reward"] > 0


def test_no_event_uses_market_led_weights():
    item = {
        "intelligence_score": 50,
        "fundamental_score": 70,
        "model_score": 60,
        "market_score": 75,
        "evidence_score": 45,
        "predicted_5d": None,
        "predicted_20d": None,
        "market": {"volatility_20d_annualized_pct": 30},
        "risk": "LOW",
        "event": {},
    }

    result = OpportunityEngine.score(item)

    assert result["weight_profile"] == "market-led"
    assert result["weights"]["market"] > result["weights"]["intelligence"]


def test_negative_prediction_reduces_opportunity_score():
    base = {
        "intelligence_score": 75,
        "fundamental_score": 70,
        "model_score": 50,
        "market_score": 55,
        "evidence_score": 65,
        "predicted_5d": 2.0,
        "predicted_20d": 5.0,
        "market": {"volatility_20d_annualized_pct": 25},
        "risk": "MEDIUM",
        "event": {"event_type": "earnings", "impact": "MEDIUM"},
    }
    negative = dict(base)
    negative["predicted_5d"] = -2.0
    negative["predicted_20d"] = -5.0

    positive_result = OpportunityEngine.score(base)
    negative_result = OpportunityEngine.score(negative)

    assert negative_result["score"] < positive_result["score"]

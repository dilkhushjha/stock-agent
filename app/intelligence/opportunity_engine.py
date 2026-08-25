from __future__ import annotations

from math import erf, sqrt


class OpportunityEngine:
    """Context-aware opportunity scoring and transparent trade metrics.

    This layer deliberately does not pretend to be a calibrated trading model.
    It combines the existing evidence scores using event-aware weights and
    derives explicit risk/return metrics so the API can explain why a stock is
    ranked highly.
    """

    DEFAULT_WEIGHTS = {
        "intelligence": 0.32,
        "fundamentals": 0.20,
        "model": 0.18,
        "market": 0.18,
        "evidence": 0.12,
    }

    EVENT_WEIGHTS = {
        "policy": {"intelligence": 0.40, "fundamentals": 0.16, "model": 0.12, "market": 0.17, "evidence": 0.15},
        "government": {"intelligence": 0.40, "fundamentals": 0.16, "model": 0.12, "market": 0.17, "evidence": 0.15},
        "regulatory": {"intelligence": 0.38, "fundamentals": 0.17, "model": 0.13, "market": 0.17, "evidence": 0.15},
        "earnings": {"intelligence": 0.24, "fundamentals": 0.30, "model": 0.14, "market": 0.20, "evidence": 0.12},
        "results": {"intelligence": 0.24, "fundamentals": 0.30, "model": 0.14, "market": 0.20, "evidence": 0.12},
        "commodity": {"intelligence": 0.34, "fundamentals": 0.18, "model": 0.12, "market": 0.18, "evidence": 0.18},
        "macro": {"intelligence": 0.38, "fundamentals": 0.14, "model": 0.12, "market": 0.18, "evidence": 0.18},
        "global": {"intelligence": 0.38, "fundamentals": 0.14, "model": 0.12, "market": 0.18, "evidence": 0.18},
        "geopolitical": {"intelligence": 0.40, "fundamentals": 0.12, "model": 0.12, "market": 0.18, "evidence": 0.18},
        "merger": {"intelligence": 0.30, "fundamentals": 0.22, "model": 0.16, "market": 0.20, "evidence": 0.12},
        "acquisition": {"intelligence": 0.30, "fundamentals": 0.22, "model": 0.16, "market": 0.20, "evidence": 0.12},
    }

    @classmethod
    def score(cls, item: dict) -> dict:
        event = item.get("event") or {}
        event_type = str(event.get("event_type") or event.get("type") or "").strip().lower()
        weights, profile = cls._weights(event_type, event)

        components = {
            "intelligence": cls._safe_score(item.get("intelligence_score")),
            "fundamentals": cls._safe_score(item.get("fundamental_score")),
            "model": cls._safe_score(item.get("model_score")),
            "market": cls._safe_score(item.get("market_score")),
            "evidence": cls._safe_score(item.get("evidence_score")),
        }
        weighted = sum(components[key] * weights[key] for key in weights)

        market = item.get("market") or {}
        risk = str(item.get("risk") or "MEDIUM").upper()
        expected_5d = cls._number(item.get("predicted_5d"))
        expected_20d = cls._number(item.get("predicted_20d"))
        annual_vol = cls._number(market.get("volatility_20d_annualized_pct")) or 25.0
        sigma_5d = max(0.5, annual_vol * sqrt(5 / 252))
        sigma_20d = max(0.8, annual_vol * sqrt(20 / 252))

        # No prediction should not manufacture a positive expected return.
        expected_5d = expected_5d if expected_5d is not None else 0.0
        expected_20d = expected_20d if expected_20d is not None else expected_5d

        target_5d = cls._target(expected_5d, sigma_5d, minimum=2.0, maximum=10.0)
        target_20d = cls._target(expected_20d, sigma_20d, minimum=4.0, maximum=18.0)
        probability_5d = cls._probability_above(target_5d, expected_5d, sigma_5d)
        probability_20d = cls._probability_above(target_20d, expected_20d, sigma_20d)

        expected_downside = max(1.5, sigma_20d * {"LOW": 0.80, "MEDIUM": 1.00, "HIGH": 1.25}.get(risk, 1.0))
        risk_reward = target_20d / expected_downside if expected_downside else None

        # The opportunity score is intentionally conservative. Strong returns
        # alone cannot overwhelm weak evidence quality or fundamentals.
        conviction_bonus = 0.0
        if expected_20d > 0 and probability_20d >= 0.65:
            conviction_bonus += 3.0
        if risk_reward is not None and risk_reward >= 2.0:
            conviction_bonus += 3.0
        if expected_20d < 0:
            conviction_bonus -= min(8.0, abs(expected_20d) * 1.5)

        score = max(0.0, min(100.0, weighted + conviction_bonus))

        return {
            "score": round(score, 1),
            "weights": {k: round(v, 3) for k, v in weights.items()},
            "weight_profile": profile,
            "score_components": {k: round(v, 1) for k, v in components.items()},
            "expected_return_5d_pct": round(expected_5d, 2) if item.get("predicted_5d") is not None else None,
            "expected_return_20d_pct": round(expected_20d, 2) if item.get("predicted_20d") is not None else None,
            "estimated_target_5d_pct": round(target_5d, 2),
            "estimated_target_20d_pct": round(target_20d, 2),
            "estimated_target_probability_5d_pct": round(probability_5d * 100, 1),
            "estimated_target_probability_20d_pct": round(probability_20d * 100, 1),
            "estimated_downside_pct": round(expected_downside, 2),
            "risk_reward": round(risk_reward, 2) if risk_reward is not None else None,
            "annualized_volatility_pct": round(annual_vol, 2),
            "methodology": "Context-weighted evidence + model-implied risk/return; probability is an estimate, not a calibrated guarantee.",
        }

    @classmethod
    def _weights(cls, event_type: str, event: dict):
        selected = None
        for key, weights in cls.EVENT_WEIGHTS.items():
            if key in event_type:
                selected = weights
                break
        if selected is None:
            selected = dict(cls.DEFAULT_WEIGHTS)
            if not event.get("title") and not event.get("description"):
                selected["intelligence"] = 0.20
                selected["market"] = 0.24
                selected["fundamentals"] = 0.22
                selected["model"] = 0.20
                selected["evidence"] = 0.14
                return selected, "market-led"

        impact = str(event.get("impact") or "").upper()
        if impact in {"HIGH", "SEVERE", "CRITICAL"}:
            selected = dict(selected)
            selected["intelligence"] += 0.04
            selected["evidence"] += 0.02
            selected["market"] -= 0.03
            selected["model"] -= 0.03
        return cls._normalize(selected), cls._profile(selected, event_type, impact)

    @staticmethod
    def _normalize(weights):
        total = sum(weights.values()) or 1.0
        return {k: v / total for k, v in weights.items()}

    @staticmethod
    def _profile(weights, event_type, impact):
        if event_type:
            label = event_type.replace("_", " ").title()
            return f"{label} · {impact.title() if impact else 'Normal'} impact"
        return "Balanced evidence"

    @staticmethod
    def _target(expected, sigma, minimum, maximum):
        # A positive target is required for a meaningful target probability.
        baseline = max(minimum, expected * 0.90, sigma * 0.55)
        return min(maximum, baseline)

    @staticmethod
    def _probability_above(target, mean, sigma):
        if sigma <= 0:
            return 1.0 if mean >= target else 0.0
        z = (target - mean) / sigma
        return max(0.02, min(0.98, 0.5 * (1 - erf(z / sqrt(2)))))

    @staticmethod
    def _number(value):
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_score(value):
        try:
            return max(0.0, min(100.0, float(value))) if value is not None else 50.0
        except (TypeError, ValueError):
            return 50.0

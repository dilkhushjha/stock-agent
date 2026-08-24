from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.intelligence.causal_intelligence import CausalIntelligence
from app.intelligence.exposure import ExposureMappingService
from app.intelligence.historical_analogues import find_historical_analogues
from app.intelligence.prediction_learning import PredictionLearning
from app.intelligence.universe_recommendation_engine import UniverseRecommendationEngine
from app.models.event import MarketEvent
from app.models.stock import Stock

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/")
def get_recommendations(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    # IMPORTANT: limit controls the output, not the search universe.
    recommendations = UniverseRecommendationEngine.build(db, limit=limit)

    for item in recommendations:
        event_id = item.get("evidence", {}).get("event_id")
        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id)) if event_id else None
        causal = CausalIntelligence.enrich_event(db, event)
        item["causal_intelligence"] = causal

        normalized_sector = ExposureMappingService.normalize_entity(item.get("sector") or "")
        if causal and causal.get("normalized_entity") == normalized_sector:
            exposure = next(
                (row for row in causal.get("exposed_stocks", []) if row.get("symbol") == item.get("symbol")),
                None,
            )
            item["sector_priority"] = "DIRECT"
            item["exposure_strength"] = exposure.get("exposure_strength") if exposure else None
        else:
            item["sector_priority"] = "SECONDARY"
            item["exposure_strength"] = None

        stock = db.scalar(select(Stock).where(Stock.symbol == item.get("symbol")))
        item["historical_analogue"] = find_historical_analogues(
            db,
            event,
            stock_id=stock.id if stock else None,
            limit=8,
        )

        analogue = item["historical_analogue"]
        summary = analogue.get("summary") if analogue else None
        if summary:
            item["historical_evidence"] = {
                "sample_count": analogue.get("sample_count", 0),
                "median_5d_return_pct": summary.get("median_5d_return_pct"),
                "average_5d_return_pct": summary.get("average_5d_return_pct"),
                "positive_5d_rate_pct": summary.get("positive_5d_rate_pct"),
                "median_10d_return_pct": summary.get("median_10d_return_pct"),
            }
        else:
            item["historical_evidence"] = {
                "sample_count": analogue.get("sample_count", 0) if analogue else 0,
                "median_5d_return_pct": None,
                "average_5d_return_pct": None,
                "positive_5d_rate_pct": None,
                "median_10d_return_pct": None,
            }

        # Prediction feedback becomes part of future opportunity ranking.
        # A stock with repeatedly successful forecasts receives a modest boost;
        # a stock with poor realised forecasts is penalised. No feedback means
        # no artificial penalty.
        learning = PredictionLearning.stock_reliability(db, stock.id if stock else -1, "5d")
        item["prediction_learning"] = learning
        if learning["samples"] >= 3:
            bias = float(learning["feedback_bias"] or 0)
            item["score"] = round(max(0.0, min(100.0, float(item.get("score") or 0) + bias)), 1)
            base_confidence = float(item.get("confidence") or 0)
            confidence_adjustment = bias / 100.0 * 0.12
            item["confidence"] = round(max(0.0, min(0.99, base_confidence + confidence_adjustment)), 3)
            item["learning_note"] = (
                f"{learning['target_hit_rate_pct']:.0f}% 5D target-hit rate across "
                f"{learning['samples']} evaluated predictions."
            )
        else:
            item["learning_note"] = "Insufficient evaluated history for stock-specific learning."

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recommendations.sort(
        key=lambda item: (
            priority_order.get(item.get("priority", "LOW"), 3),
            0 if item.get("sector_priority") == "DIRECT" else 1,
            -(float(item.get("score") or 0)),
        )
    )
    for index, item in enumerate(recommendations, 1):
        item["rank"] = index

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "universe_scanned": max((x.get("universe_scanned", 0) for x in recommendations), default=0),
        "recommendations": recommendations[:limit],
    }

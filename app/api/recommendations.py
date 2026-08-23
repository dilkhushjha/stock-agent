from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.intelligence.causal_intelligence import CausalIntelligence
from app.intelligence.exposure import ExposureMappingService
from app.intelligence.universe_recommendation_engine import UniverseRecommendationEngine
from app.models.event import MarketEvent

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/")
def get_recommendations(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    # IMPORTANT: limit controls the output, not the search universe.
    # The engine scans the active NSE universe first and only then selects the
    # strongest ideas.
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

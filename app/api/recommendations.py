from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.intelligence.recommendation_engine import RecommendationEngine

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/")
def get_recommendations(
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    return {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
        "recommendations": RecommendationEngine.build(db, limit=limit),
    }

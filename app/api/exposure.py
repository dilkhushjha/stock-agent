from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.data.database import get_db

from app.intelligence.exposure_service import (
    ExposureService,
)


router = APIRouter(
    prefix="/exposure",
    tags=["Exposure"],
)


@router.post("/seed")
def seed_exposures(
    db: Session = Depends(get_db),
):

    return ExposureService.seed(db)
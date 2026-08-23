from fastapi import APIRouter

from app.intelligence.sector_intelligence import (
    SectorIntelligence,
)


router = APIRouter(
    prefix="/sectors",
    tags=["Sector Intelligence"],
)


@router.get("/")
def get_all_sectors():

    return SectorIntelligence.get_all()


@router.get("/{sector}")
def get_sector(
    sector: str,
):

    return (
        SectorIntelligence
        .get_sector_data(sector)
    )
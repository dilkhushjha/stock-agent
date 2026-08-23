from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.intelligence.nse_universe import NSEUniverseService

router = APIRouter(prefix="/universe", tags=["Universe"])


@router.post("/sync")
def sync_nse_universe(db: Session = Depends(get_db)):
    """Import the current NSE equity master before broad recommendation scans."""
    return NSEUniverseService.sync(db)

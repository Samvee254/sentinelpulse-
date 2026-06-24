from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=list[schemas.AlertOut])
def list_alerts(region: Optional[str] = None, limit: int = 30, db: Session = Depends(get_db)):
    """
    The mobile app's main feed screen calls this. Optionally filter by
    region (e.g. 'Nairobi') once you have region-tagged alerts.
    """
    query = db.query(models.Alert).order_by(models.Alert.published_at.desc())
    if region:
        query = query.filter(models.Alert.region == region)
    return query.limit(limit).all()


@router.get("/campaigns", response_model=list[schemas.CampaignOut])
def list_campaigns(active_only: bool = True, db: Session = Depends(get_db)):
    """Active scam campaigns the system has detected via correlation."""
    query = db.query(models.Campaign)
    if active_only:
        query = query.filter(models.Campaign.active == True)  # noqa: E712
    return query.order_by(models.Campaign.created_at.desc()).all()

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/", response_model=schemas.StatsOut)
def get_stats(db: Session = Depends(get_db)):
    """
    Aggregate counts for a simple dashboard view -- total URLs scanned,
    reports submitted, alerts published, active campaigns, plus a
    breakdown of URLs by status and by detection source.
    """
    total_urls = db.query(func.count(models.Url.id)).scalar() or 0
    total_reports = db.query(func.count(models.Report.id)).scalar() or 0
    total_alerts = db.query(func.count(models.Alert.id)).scalar() or 0
    active_campaigns = (
        db.query(func.count(models.Campaign.id))
        .filter(models.Campaign.active == True)  # noqa: E712
        .scalar()
        or 0
    )

    status_rows = (
        db.query(models.Url.status, func.count(models.Url.id))
        .group_by(models.Url.status)
        .all()
    )
    urls_by_status = {status: count for status, count in status_rows}

    source_rows = (
        db.query(models.FeedSource.name, func.count(models.Url.id))
        .join(models.Url, models.Url.source_id == models.FeedSource.id)
        .group_by(models.FeedSource.name)
        .all()
    )
    urls_by_source = {name: count for name, count in source_rows}

    return schemas.StatsOut(
        total_urls=total_urls,
        total_reports=total_reports,
        total_alerts=total_alerts,
        active_campaigns=active_campaigns,
        urls_by_status=urls_by_status,
        urls_by_source=urls_by_source,
    )

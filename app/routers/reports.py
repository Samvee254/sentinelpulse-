from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/", response_model=schemas.ReportOut)
def submit_report(payload: schemas.ReportCreate, db: Session = Depends(get_db)):
    """
    Submit a scam report from the mobile app. This is a secondary signal --
    it doesn't drive detection on its own, but feeds the correlation logic
    that groups reports into campaigns (see app/ingest/correlate.py).
    """
    url_id = None
    if payload.url:
        existing = db.query(models.Url).filter(models.Url.url == payload.url).first()
        if existing:
            url_id = existing.id
        else:
            new_url = models.Url(url=payload.url, domain=payload.url, risk_score=0.0)
            db.add(new_url)
            db.commit()
            db.refresh(new_url)
            url_id = new_url.id

    report = models.Report(
        url_id=url_id,
        phone_number=payload.phone_number,
        description=payload.description,
        reporter_contact=payload.reporter_contact,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/", response_model=list[schemas.ReportOut])
def list_reports(limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(models.Report)
        .order_by(models.Report.created_at.desc())
        .limit(limit)
        .all()
    )

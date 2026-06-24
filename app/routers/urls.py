from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..scoring import score_url

router = APIRouter(prefix="/urls", tags=["urls"])


@router.post("/check", response_model=schemas.UrlCheckResponse)
def check_url(payload: schemas.UrlCheckRequest, db: Session = Depends(get_db)):
    """
    The core 'is this link safe' endpoint the mobile app calls.
    Looks up existing scoring if we've seen this URL, otherwise scores it
    fresh and stores it.
    """
    existing = db.query(models.Url).filter(models.Url.url == payload.url).first()

    if existing:
        return schemas.UrlCheckResponse(
            url=existing.url,
            domain=existing.domain,
            risk_score=existing.risk_score,
            status=existing.status,
            domain_age_days=existing.domain_age_days,
            reasons=["previously scored by SentinelPulse"],
        )

    result = score_url(payload.url)

    new_url = models.Url(
        url=payload.url,
        domain=result["domain"],
        risk_score=result["risk_score"],
        status=result["status"],
        domain_age_days=result["domain_age_days"],
    )
    db.add(new_url)
    db.commit()
    db.refresh(new_url)

    return schemas.UrlCheckResponse(
        url=new_url.url,
        domain=new_url.domain,
        risk_score=new_url.risk_score,
        status=new_url.status,
        domain_age_days=new_url.domain_age_days,
        reasons=result["reasons"],
    )


@router.get("/recent", response_model=list[schemas.UrlCheckResponse])
def recent_urls(limit: int = 20, db: Session = Depends(get_db)):
    """Most recently seen flagged URLs -- useful for an analyst/admin view."""
    urls = (
        db.query(models.Url)
        .order_by(models.Url.last_seen.desc())
        .limit(limit)
        .all()
    )
    return [
        schemas.UrlCheckResponse(
            url=u.url,
            domain=u.domain,
            risk_score=u.risk_score,
            status=u.status,
            domain_age_days=u.domain_age_days,
            reasons=[],
        )
        for u in urls
    ]

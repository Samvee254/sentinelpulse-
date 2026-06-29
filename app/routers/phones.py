from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/phones", tags=["phones"])


def risk_level_for_count(count: int) -> str:
    """
    Mirrors the severity thresholds used in app/ingest/correlate.py, so a
    number's risk level here stays consistent with what triggers a campaign.
    Below the campaign threshold (3), we still surface a "low" risk rather
    than calling it safe -- a couple of independent reports is real signal,
    just not yet enough to auto-generate a campaign alert.
    """
    if count == 0:
        return "unknown"
    if count >= 10:
        return "critical"
    if count >= 5:
        return "high"
    if count >= 3:
        return "medium"
    return "low"


@router.post("/check", response_model=schemas.PhoneCheckResponse)
def check_phone(payload: schemas.PhoneCheckRequest, db: Session = Depends(get_db)):
    """
    Look up how many times a phone number has been reported, and whether
    it's already part of a detected scam campaign. This is a lookup, not
    a write -- checking a number doesn't itself create a report.
    """
    phone = payload.phone_number.strip()

    report_count = (
        db.query(models.Report)
        .filter(models.Report.phone_number == phone)
        .count()
    )

    campaign_link = (
        db.query(models.Campaign)
        .join(models.CampaignLink, models.CampaignLink.campaign_id == models.Campaign.id)
        .join(models.Report, models.CampaignLink.report_id == models.Report.id)
        .filter(models.Report.phone_number == phone, models.Campaign.active == True)  # noqa: E712
        .first()
    )

    reasons = []
    if report_count == 0:
        reasons.append("no reports found for this number yet")
    else:
        reasons.append(f"reported {report_count} time(s) by SentinelPulse users")
    if campaign_link:
        reasons.append("part of an active detected scam campaign")

    return schemas.PhoneCheckResponse(
        phone_number=phone,
        report_count=report_count,
        risk_level=risk_level_for_count(report_count),
        in_active_campaign=campaign_link is not None,
        campaign_title=campaign_link.title if campaign_link else None,
        reasons=reasons,
    )

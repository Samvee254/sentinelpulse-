"""
Groups related, uncorrelated reports into a Campaign when enough of them
share a signal (same domain or same phone number). This is the piece that
turns "scattered individual reports" into "a detected scam campaign".

Run manually with:
    python -m app.ingest.correlate

Deliberately simple (no ML/clustering) for v1 -- exact-match grouping on
phone_number and url.domain. Swap in fuzzy matching or embeddings later
once you have enough real report volume to justify it.
"""
from collections import defaultdict

from ..database import SessionLocal
from .. import models

MIN_REPORTS_FOR_CAMPAIGN = 3


def group_by_phone(db) -> dict:
    reports = (
        db.query(models.Report)
        .filter(models.Report.phone_number.isnot(None))
        .all()
    )
    groups = defaultdict(list)
    for r in reports:
        groups[r.phone_number].append(r)
    return groups


def group_by_domain(db) -> dict:
    reports = (
        db.query(models.Report)
        .join(models.Url, models.Report.url_id == models.Url.id)
        .all()
    )
    groups = defaultdict(list)
    for r in reports:
        groups[r.url.domain].append(r)
    return groups


def already_in_campaign(db, report: models.Report) -> bool:
    return (
        db.query(models.CampaignLink)
        .filter(models.CampaignLink.report_id == report.id)
        .first()
        is not None
    )


def create_campaign_from_reports(db, key: str, reports: list, severity: str):
    campaign = models.Campaign(
        title=f"Suspected scam campaign: {key}",
        description=f"{len(reports)} reports linked by shared signal '{key}'.",
        severity=severity,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    for report in reports:
        db.add(models.CampaignLink(campaign_id=campaign.id, report_id=report.id))
        if report.url_id:
            db.add(models.CampaignLink(campaign_id=campaign.id, url_id=report.url_id))

    alert = models.Alert(
        campaign_id=campaign.id,
        title=campaign.title,
        message=(
            f"SentinelPulse has detected {len(reports)} related reports "
            f"linked by '{key}'. Avoid interacting with this number/link."
        ),
        severity=severity,
    )
    db.add(alert)
    db.commit()
    return campaign


def severity_for_count(count: int) -> str:
    if count >= 10:
        return "critical"
    if count >= 5:
        return "high"
    return "medium"


def main():
    db = SessionLocal()
    created = 0
    try:
        for grouping in (group_by_phone(db), group_by_domain(db)):
            for key, reports in grouping.items():
                if len(reports) < MIN_REPORTS_FOR_CAMPAIGN:
                    continue
                unlinked = [r for r in reports if not already_in_campaign(db, r)]
                if len(unlinked) < MIN_REPORTS_FOR_CAMPAIGN:
                    continue
                create_campaign_from_reports(db, key, unlinked, severity_for_count(len(unlinked)))
                created += 1
        print(f"Created {created} new campaign(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""
Pulls phishing URLs from public threat intel feeds and scores them.

Run manually with:
    python -m app.ingest.fetch_feeds

In production, schedule this with cron (e.g. every 30 minutes) or a simple
background worker. This is intentionally simple -- no message queue, no
async, just a script that runs and exits. Grow it later if needed.

NOTE: this fetches real external feeds, so you'll need outbound internet
access from wherever you deploy/run it.
"""
import requests

from ..database import SessionLocal, Base, engine
from .. import models
from ..scoring import score_url

OPENPHISH_FEED_URL = "https://openphish.com/feed.txt"  # community feed, rate-limited
URLHAUS_FEED_URL = "https://urlhaus.abuse.ch/downloads/text_recent/"
THREATFOX_FEED_URL = "https://threatfox.abuse.ch/export/json/recent/"

# ThreatFox lists many IOC types (hashes, registry keys, etc.) -- we only
# want the ones that map to something we can score as a URL/domain.
THREATFOX_RELEVANT_TYPES = {"url", "domain", "ip:port"}


def fetch_openphish() -> list[str]:
    try:
        resp = requests.get(OPENPHISH_FEED_URL, timeout=15)
        resp.raise_for_status()
        return [line.strip() for line in resp.text.splitlines() if line.strip()]
    except requests.RequestException as e:
        print(f"[fetch_openphish] failed: {e}")
        return []


def fetch_urlhaus() -> list[str]:
    try:
        resp = requests.get(URLHAUS_FEED_URL, timeout=15)
        resp.raise_for_status()
        return [
            line.strip()
            for line in resp.text.splitlines()
            if line.strip() and not line.startswith("#")
        ]
    except requests.RequestException as e:
        print(f"[fetch_urlhaus] failed: {e}")
        return []


def fetch_threatfox() -> list[str]:
    """
    ThreatFox (abuse.ch) tracks malware C2 infrastructure -- a different
    angle than OpenPhish (phishing sites) and URLhaus (malware downloads).
    Response shape: {"<id>": [{"ioc_value": ..., "ioc_type": ..., ...}]}
    """
    try:
        resp = requests.get(THREATFOX_FEED_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # A clean feed with zero new IOCs returns a status dict, not IOC entries.
        if not isinstance(data, dict):
            return []

        values = []
        for entries in data.values():
            for entry in entries:
                if entry.get("ioc_type") in THREATFOX_RELEVANT_TYPES:
                    values.append(entry["ioc_value"])
        return values
    except (requests.RequestException, ValueError) as e:
        print(f"[fetch_threatfox] failed: {e}")
        return []


def get_or_create_source(db, name: str, source_type: str) -> models.FeedSource:
    source = db.query(models.FeedSource).filter_by(name=name).first()
    if not source:
        source = models.FeedSource(name=name, source_type=source_type)
        db.add(source)
        db.commit()
        db.refresh(source)
    return source


def ingest_urls(db, urls: list[str], source: models.FeedSource):
    """
    Bulk-checks which URLs already exist, in batches, instead of querying
    the database once per URL (which is painfully slow over a network
    connection to a hosted database once feeds have thousands of entries).
    """
    if not urls:
        return 0

    # The url column is VARCHAR(2048). A handful of feed entries are
    # absurdly long (encoded tokens, etc.) and would fail the insert --
    # skip those rather than crashing the whole batch.
    MAX_URL_LENGTH = 2000
    too_long = sum(1 for u in urls if len(u) > MAX_URL_LENGTH)
    urls = [u for u in urls if len(u) <= MAX_URL_LENGTH]
    if too_long:
        print(f"  (skipped {too_long} URL(s) exceeding {MAX_URL_LENGTH} characters)")

    CHUNK_SIZE = 1000
    existing_urls = set()
    for i in range(0, len(urls), CHUNK_SIZE):
        chunk = urls[i:i + CHUNK_SIZE]
        rows = db.query(models.Url.url).filter(models.Url.url.in_(chunk)).all()
        existing_urls.update(row.url for row in rows)

    new_count = 0
    for raw_url in urls:
        if raw_url in existing_urls:
            continue

        result = score_url(raw_url, is_on_feed=True, check_domain_age=False)
        record = models.Url(
            url=raw_url,
            domain=result["domain"],
            source_id=source.id,
            risk_score=result["risk_score"],
            status=result["status"],
            domain_age_days=result["domain_age_days"],
        )
        db.add(record)
        new_count += 1
        existing_urls.add(raw_url)  # guard against duplicates within the same feed

    db.commit()
    return new_count


def run_feed(db, name: str, source_type: str, fetch_fn):
    """Run one feed end-to-end, isolated so a failure here doesn't block the rest."""
    try:
        source = get_or_create_source(db, name, source_type)
        urls = fetch_fn()
        added = ingest_urls(db, urls, source)
        print(f"{name}: fetched {len(urls)}, added {added} new")
    except Exception as e:
        db.rollback()  # clear the failed transaction so the next feed can still run
        print(f"{name}: FAILED -- {e}")


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        run_feed(db, "OpenPhish", "phishing_feed", fetch_openphish)
        run_feed(db, "URLhaus", "malware_feed", fetch_urlhaus)
        run_feed(db, "ThreatFox", "malware_cc_feed", fetch_threatfox)
    finally:
        db.close()


if __name__ == "__main__":
    main()

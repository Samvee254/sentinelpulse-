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

OPENPHISH_FEED_URL = "https://openphish.com/feed.txt"
URLHAUS_FEED_URL = "https://urlhaus.abuse.ch/downloads/text_recent/"


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
        existing_urls.add(raw_url)

    db.commit()
    return new_count


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        openphish_source = get_or_create_source(db, "OpenPhish", "phishing_feed")
        openphish_urls = fetch_openphish()
        added = ingest_urls(db, openphish_urls, openphish_source)
        print(f"OpenPhish: fetched {len(openphish_urls)}, added {added} new")

        urlhaus_source = get_or_create_source(db, "URLhaus", "malware_feed")
        urlhaus_urls = fetch_urlhaus()
        added = ingest_urls(db, urlhaus_urls, urlhaus_source)
        print(f"URLhaus: fetched {len(urlhaus_urls)}, added {added} new")
    finally:
        db.close()


if __name__ == "__main__":
    main()

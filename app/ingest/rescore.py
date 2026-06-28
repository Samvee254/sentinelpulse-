"""
One-time utility: re-scores all existing feed-sourced URLs using the
current scoring logic. Needed whenever scoring.py's weights change --
otherwise old rows keep their stale scores forever, since normal
ingestion only scores brand-new URLs, never revisits existing ones.

Uses psycopg2's execute_values for a genuine single-round-trip bulk
UPDATE -- SQLAlchemy's ORM (even bulk_update_mappings) still sends one
UPDATE per row under the hood with the default driver, which is far too
slow for ~30k rows over a network connection to a hosted database.

Run manually with:
    python -m app.ingest.rescore
"""
import psycopg2
import psycopg2.extras

from ..database import DATABASE_URL
from ..database import SessionLocal
from .. import models
from ..scoring import score_url

BATCH_SIZE = 2000


def main():
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Url.id, models.Url.url, models.Url.domain_age_days)
            .filter(models.Url.source_id.isnot(None))
            .all()
        )
        print(f"Re-scoring {len(rows)} feed-sourced URLs...")

        updates = []
        for row_id, url, domain_age_days in rows:
            result = score_url(
                url,
                domain_age_days=domain_age_days,
                is_on_feed=True,
                check_domain_age=False,
            )
            updates.append((row_id, result["risk_score"], result["status"]))
    finally:
        db.close()

    print(f"Writing {len(updates)} updates in batches of {BATCH_SIZE}...")

    # Bypass the ORM entirely for this part -- raw psycopg2 + execute_values
    # is what actually gives us one real round trip per batch.
    pg_url = DATABASE_URL.replace("postgresql://", "postgres://", 1)
    conn = psycopg2.connect(pg_url)
    try:
        with conn.cursor() as cur:
            for i in range(0, len(updates), BATCH_SIZE):
                batch = updates[i:i + BATCH_SIZE]
                psycopg2.extras.execute_values(
                    cur,
                    """
                    UPDATE urls AS u
                    SET risk_score = v.risk_score, status = v.status
                    FROM (VALUES %s) AS v(id, risk_score, status)
                    WHERE u.id = v.id
                    """,
                    batch,
                    template="(%s, %s, %s)",
                )
                print(f"  batch {i // BATCH_SIZE + 1}: {len(batch)} rows")
        conn.commit()
        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

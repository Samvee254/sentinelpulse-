# SentinelPulse

Kenya's cyber early-warning system. See threats before they spread.

This is the backend: a FastAPI app, a database schema for tracking
flagged URLs, user reports, detected scam campaigns, and the alerts shown
in the mobile app.

Live API: https://sentinelpulse-api-v8sz.onrender.com
Interactive docs: https://sentinelpulse-api-v8sz.onrender.com/docs
## Project structure

sentinelpulse/app/main.py - FastAPI entrypoint
sentinelpulse/app/database.py - DB connection (SQLite by default, swap to Postgres)
sentinelpulse/app/models.py - SQLAlchemy ORM tables
sentinelpulse/app/schemas.py - Pydantic request/response shapes
sentinelpulse/app/scoring.py - Rule-based risk scoring engine plus WHOIS lookup
sentinelpulse/app/routers/urls.py - POST /urls/check, GET /urls/recent
sentinelpulse/app/routers/reports.py - POST /reports, GET /reports
sentinelpulse/app/routers/alerts.py - GET /alerts, GET /alerts/campaigns
sentinelpulse/app/ingest/fetch_feeds.py - Pulls from OpenPhish and URLhaus automatically
sentinelpulse/app/ingest/correlate.py - Groups reports into detected campaigns

## Setup

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

## Run the API

uvicorn app.main:app --reload

Visit http://127.0.0.1:8000/docs for interactive API docs.

## Run automated feed ingestion (proactive detection)

python -m app.ingest.fetch_feeds

Pulls phishing/malware URLs from OpenPhish and URLhaus automatically.
No reporter required. Schedule with cron every 15-30 min in production.

## Run the correlation job (turns reports into campaigns)

python -m app.ingest.correlate

Groups 3+ reports sharing a phone number or domain into a campaign and
auto-generates an alert.

## Switching to Postgres

Set DATABASE_URL in a .env file:

DATABASE_URL=postgresql://user:password@host:5432/sentinelpulse

## Roadmap

- Push notifications instead of polling /alerts
- Web dashboard for analyst view
- Social media keyword scanning
- ML-based scoring once labeled data exists

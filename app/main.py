"""
SentinelPulse API entrypoint.

Run locally with:
    uvicorn app.main:app --reload

Then visit http://127.0.0.1:8000/docs for interactive API docs.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import urls, reports, alerts, stats

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SentinelPulse API",
    description="Kenya's cyber early-warning system -- see threats before they spread.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this once you know your real frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(urls.router)
app.include_router(reports.router)
app.include_router(alerts.router)
app.include_router(stats.router)


@app.get("/")
def root():
    return {"service": "SentinelPulse API", "status": "running"}

"""
Pydantic schemas for SentinelPulse's API requests and responses.
Kept separate from the SQLAlchemy models (app/models.py) on purpose --
this is what the API actually exposes to clients.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class UrlCheckRequest(BaseModel):
    url: str


class UrlCheckResponse(BaseModel):
    url: str
    domain: str
    risk_score: float
    status: str
    domain_age_days: Optional[int] = None
    reasons: list[str] = []


class ReportCreate(BaseModel):
    url: Optional[str] = None
    phone_number: Optional[str] = None
    description: Optional[str] = None
    reporter_contact: Optional[str] = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone_number: Optional[str] = None
    description: Optional[str] = None
    verified: bool
    created_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    severity: str
    region: Optional[str] = None
    published_at: datetime


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    severity: str
    region: Optional[str] = None
    active: bool
    created_at: datetime

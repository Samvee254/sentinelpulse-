"""
SQLAlchemy models for SentinelPulse, matching the ERD:

FeedSource --< Url --< Report
Url, Report >--< Campaign (via CampaignLink)
Campaign, Url --< Alert
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class FeedSource(Base):
    """A threat intel feed SentinelPulse pulls from, e.g. PhishTank, OpenPhish."""
    __tablename__ = "feed_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    source_type = Column(String(50), nullable=False)
    last_synced_at = Column(DateTime, nullable=True)

    urls = relationship("Url", back_populates="source")


class Url(Base):
    """A URL/domain that has been flagged by a feed or scored by the engine."""
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False, unique=True, index=True)
    domain = Column(String(255), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("feed_sources.id"), nullable=True)

    domain_age_days = Column(Integer, nullable=True)
    risk_score = Column(Float, default=0.0)
    status = Column(String(30), default="pending")

    first_seen = Column(DateTime, server_default=func.now())
    last_seen = Column(DateTime, server_default=func.now(), onupdate=func.now())

    source = relationship("FeedSource", back_populates="urls")
    reports = relationship("Report", back_populates="url")
    campaign_links = relationship("CampaignLink", back_populates="url")
    alerts = relationship("Alert", back_populates="url")


class Report(Base):
    """A scam/phishing report submitted by a user via the mobile app."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True)
    url_id = Column(Integer, ForeignKey("urls.id"), nullable=True)

    phone_number = Column(String(30), nullable=True)
    description = Column(Text, nullable=True)
    reporter_contact = Column(String(100), nullable=True)
    verified = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())

    url = relationship("Url", back_populates="reports")
    campaign_links = relationship("CampaignLink", back_populates="report")


class Campaign(Base):
    """A cluster of related reports/urls that the system has grouped together."""
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), default="low")
    region = Column(String(100), nullable=True)
    active = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    links = relationship("CampaignLink", back_populates="campaign")
    alerts = relationship("Alert", back_populates="campaign")


class CampaignLink(Base):
    """Join table linking urls and/or reports into a campaign cluster."""
    __tablename__ = "campaign_links"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    url_id = Column(Integer, ForeignKey("urls.id"), nullable=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)

    campaign = relationship("Campaign", back_populates="links")
    url = relationship("Url", back_populates="campaign_links")
    report = relationship("Report", back_populates="campaign_links")


class Alert(Base):
    """A published alert shown in the mobile app's feed."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    url_id = Column(Integer, ForeignKey("urls.id"), nullable=True)

    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), default="low")
    region = Column(String(100), nullable=True)

    published_at = Column(DateTime, server_default=func.now())

    campaign = relationship("Campaign", back_populates="alerts")
    url = relationship("Url", back_populates="alerts")

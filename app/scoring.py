"""
Risk scoring engine for SentinelPulse.

v1 keeps this deliberately simple and rule-based -- no ML yet. The point is
to have something that produces a real, explainable score from real signals
(domain age, keyword match, known-bad-list hit) before reaching for AI.
"""
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import whois

# Brands commonly impersonated in Kenyan phishing campaigns.
# Extend this list as you find more in the feeds.
KENYA_KEYWORDS = [
    "mpesa", "m-pesa", "safaricom", "kcb", "equity", "equitybank",
    "helb", "ecitizen", "kra", "nhif", "sha", "co-op", "cooperative",
    "absa", "ncba", "stanbic", "dtb",
]


def extract_domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return parsed.netloc.lower()


def keyword_score(url: str) -> tuple[float, list[str]]:
    """Flag if the URL impersonates a known Kenyan brand in its text."""
    lowered = url.lower()
    hits = [kw for kw in KENYA_KEYWORDS if kw in lowered]
    score = min(len(hits) * 25, 50)
    reasons = [f"contains brand keyword '{kw}'" for kw in hits]
    return score, reasons
# TLDs that are cheap and easy to register anonymously, and disproportionately
# used for short-lived scam/phishing campaigns. Not proof of malice on their
# own, but a real signal worth weighting.
SUSPICIOUS_TLDS = [
    ".click", ".tk", ".xyz", ".top", ".work", ".loan", ".win",
    ".bid", ".men", ".gq", ".cf", ".ml", ".ga", ".icu", ".cam",
]


def tld_score(domain: str) -> tuple[float, list[str]]:
    """Flag domains using TLDs that are cheap, anonymous, and scam-favored."""
    lowered = domain.lower()
    for tld in SUSPICIOUS_TLDS:
        if lowered.endswith(tld):
            return 20.0, [f"uses suspicious top-level domain '{tld}'"]
    return 0.0, []

def lookup_domain_age_days(domain: str) -> Optional[int]:
    """
    Real WHOIS lookup for how old a domain registration is.
    Returns None if the lookup fails -- WHOIS servers are unreliable and
    rate-limited, so this must never crash the caller.
    """
    try:
        record = whois.whois(domain)
        creation_date = record.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        if creation_date is None:
            return None
        if creation_date.tzinfo is None:
            creation_date = creation_date.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - creation_date
        return max(age.days, 0)
    except Exception:
        return None


def domain_age_score(domain_age_days: Optional[int] = None) -> tuple[float, list[str]]:
    """Newly registered domains are disproportionately used for phishing."""
    if domain_age_days is None:
        return 0.0, []
    if domain_age_days < 7:
        return 30.0, ["domain registered less than 7 days ago"]
    if domain_age_days < 30:
        return 15.0, ["domain registered less than 30 days ago"]
    return 0.0, []


def blacklist_score(is_on_feed: bool) -> tuple[float, list[str]]:
    """Direct hit on a known threat intel feed (PhishTank/OpenPhish/URLhaus)."""
    if is_on_feed:
        return 40.0, ["matched a known threat intelligence feed"]
    return 0.0, []


def score_url(
    url: str,
    domain_age_days: Optional[int] = None,
    is_on_feed: bool = False,
    check_domain_age: bool = True,
) -> dict:
    """
    Combine signals into a single 0-100 risk score plus human-readable reasons.
    If domain_age_days isn't passed in, this does a live WHOIS lookup itself
    (set check_domain_age=False to skip it, e.g. during bulk feed ingestion).
    """
    domain = extract_domain(url)

    if domain_age_days is None and check_domain_age:
        domain_age_days = lookup_domain_age_days(domain)

    reasons: list[str] = []
    total = 0.0

    s, r = keyword_score(url)
    total += s
    reasons += r

    s, r = domain_age_score(domain_age_days)
    total += s
    reasons += r

    s, r = blacklist_score(is_on_feed)
    total += s
    reasons += r

    s, r = tld_score(domain)
    total += s
    reasons += r

    total = min(total, 100.0)

    if total >= 70:
        status = "confirmed"
    elif total >= 30:
        status = "pending"
    else:
        status = "dismissed"

    return {
        "domain": domain,
        "risk_score": total,
        "status": status,
        "domain_age_days": domain_age_days,
        "reasons": reasons or ["no risk signals detected"],
    }

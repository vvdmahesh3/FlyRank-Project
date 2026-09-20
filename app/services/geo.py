"""Geo enrichment with a fallback chain.

Provider A (ip-api.com) → Provider B (ipinfo.io) → Store without geo.

Both providers are free (no credit card):
- ip-api.com: 45 req/min, no key, returns JSON via HTTP
- ipinfo.io: 50k req/month, token optional (free tier)

If both fail, the submission is still stored — geo is nullable. This is
"graceful degradation": enrichment is a nice-to-have, not a hard dependency.
"""

import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GEO_RESULT = dict  # {"country": str, "region": str, "city": str, "lat": float, "lon": float, "provider": str}


def _enrich_ip_api(ip: str) -> Optional[GEO_RESULT]:
    """Provider A: ip-api.com (free, no key)."""
    try:
        resp = httpx.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,regionName,city,lat,lon"},
            timeout=3.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            return None
        return {
            "country": data.get("country"),
            "region": data.get("regionName"),
            "city": data.get("city"),
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "provider": "ip-api",
        }
    except Exception as exc:
        logger.warning("ip-api enrichment failed for %s: %s", ip, exc)
        return None


def _enrich_ipinfo(ip: str) -> Optional[GEO_RESULT]:
    """Provider B: ipinfo.io (free tier, token optional)."""
    try:
        headers = {}
        if settings.geo_fallback_token:
            headers["Authorization"] = f"Bearer {settings.geo_fallback_token}"
        resp = httpx.get(
            f"https://ipinfo.io/{ip}/json",
            headers=headers,
            timeout=3.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if "country" not in data:
            return None
        lat, lon = None, None
        if loc := data.get("loc", "").split(","):
            if len(loc) == 2:
                lat, lon = float(loc[0]), float(loc[1])
        return {
            "country": data.get("country"),
            "region": data.get("region"),
            "city": data.get("city"),
            "lat": lat,
            "lon": lon,
            "provider": "ipinfo",
        }
    except Exception as exc:
        logger.warning("ipinfo enrichment failed for %s: %s", ip, exc)
        return None


def enrich_ip(ip: str) -> Optional[GEO_RESULT]:
    """Run the fallback chain: primary → fallback → None.

    Returns a dict or None. None means store without geo — never raise.
    """
    if not ip or ip in ("127.0.0.1", "localhost", "::1"):
        return None

    primary = _enrich_ip_api(ip)
    if primary:
        return primary

    fallback = _enrich_ipinfo(ip)
    if fallback:
        return fallback

    logger.info("All geo providers failed for %s — storing without geo", ip)
    return None

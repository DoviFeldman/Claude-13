"""Xweather (formerly Aeris) lightning API - the primary source.

Pay-as-you-go plan: first 15,000 accesses/month are free, which comfortably
covers this project's schedule (~1,600 runs/month, one access per run).
Docs: https://www.xweather.com/docs/weather-api/endpoints/lightning
"""

import logging

import requests

from .base import Strike, ProviderError

log = logging.getLogger(__name__)

BASE_URL = "https://data.api.xweather.com/lightning"


def fetch(cfg):
    """One API access: all strikes within max_range_km over the lookback window."""
    params = {
        "client_id": cfg.xweather_client_id,
        "client_secret": cfg.xweather_client_secret,
        "radius": f"{int(cfg.max_range_km)}km",
        "from": f"-{cfg.lookback_minutes}minutes",
        "limit": 250,
        "format": "json",
    }
    url = f"{BASE_URL}/{cfg.target_lat},{cfg.target_lon}"
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        raise ProviderError(f"xweather request failed: {exc}") from exc

    if not payload.get("success"):
        err = (payload.get("error") or {}).get("code", "unknown")
        # "warn_no_data" just means a quiet sky, not a failure.
        if err == "warn_no_data":
            return []
        raise ProviderError(f"xweather error: {err}")

    strikes = []
    for ob in payload.get("response") or []:
        try:
            loc = ob["loc"]
            when = (ob.get("ob") or {}).get("dateTimeISO") or ob.get("dateTimeISO", "")
            strikes.append(Strike(
                lat=float(loc["lat"]),
                lon=float(loc["long"]),
                time_utc=when,
                source="xweather",
            ))
        except (KeyError, TypeError, ValueError):
            log.warning("xweather: skipping malformed record: %r", ob)
    return strikes

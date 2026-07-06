"""Offshore lightning storm detector.

Each run:
  1. checks the schedule window (7 PM - midnight Eastern, not Friday)
  2. pulls recent strikes from every enabled source (Xweather primary,
     GOES GLM + Blitzortung for comparison)
  3. classifies each strike into a distance band from the target coordinate
  4. sends a Telegram alert for the 30-60 km sweet spot (primary trigger)
     or a lower-frequency "approaching" warning for the 60-250 km wide zone
  5. writes docs/data/strikes.json for the map site

Run: python -m detector.main
"""

import datetime as dt
import json
import logging
import pathlib
import statistics
import sys
from zoneinfo import ZoneInfo

from . import alerting, state as state_mod
from .config import Config
from .geo import (DANGER_LIMIT, MAX_RANGE_KM, SWEET_SPOT, WIDE_ZONE,
                  classify_band, compass_point, haversine_km, initial_bearing_deg)
from .providers import enabled_providers
from .providers.base import ProviderError

log = logging.getLogger("detector")

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
STRIKES_PATH = REPO_ROOT / "docs" / "data" / "strikes.json"

EASTERN = ZoneInfo("America/New_York")
WINDOW_START_HOUR = 19  # 7 PM ET; window runs to midnight
SKIP_WEEKDAY = 4        # Friday night is off


def in_schedule_window(now_local):
    """True when we're inside 7 PM - midnight ET on a non-Friday.

    Cron fires in UTC; doing the day/hour check here in America/New_York
    handles DST for free.
    """
    return now_local.weekday() != SKIP_WEEKDAY and now_local.hour >= WINDOW_START_HOUR


def enrich(strikes, cfg):
    """Attach distance/bearing/band to each strike; drop anything beyond range."""
    kept = []
    for s in strikes:
        s.distance_km = haversine_km(cfg.target_lat, cfg.target_lon, s.lat, s.lon)
        if s.distance_km > MAX_RANGE_KM:
            continue
        s.bearing_deg = initial_bearing_deg(cfg.target_lat, cfg.target_lon, s.lat, s.lon)
        band = classify_band(s.distance_km)
        if band:
            s.band, s.severity = band
        kept.append(s)
    return kept


def in_zone(strikes, zone):
    lo, hi = zone
    return [s for s in strikes if lo <= s.distance_km < hi]


def summarize(strikes, all_strikes):
    """Stats for an alert: counts, closest strike, plus any danger-zone strikes."""
    distances = [s.distance_km for s in strikes]
    closest = min(strikes, key=lambda s: s.distance_km)
    return {
        "count": len(strikes),
        "min_km": min(distances),
        "median_km": statistics.median(distances),
        "closest_bearing": closest.bearing_deg,
        "closest_compass": compass_point(closest.bearing_deg),
        "closest_band": closest.band,
        "danger_count": sum(1 for s in all_strikes if s.distance_km < DANGER_LIMIT),
    }


def write_strikes_json(all_strikes, source_counts, now_utc):
    STRIKES_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {name: {"ok": info["ok"], "count": info["count"]}
                    for name, info in source_counts.items()},
        "strikes": [s.to_public_dict() for s in all_strikes],
    }
    STRIKES_PATH.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    log.info("wrote %s (%d strikes)", STRIKES_PATH, len(all_strikes))


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = Config.from_env()
    if cfg.missing:
        log.error("missing required secrets: %s", ", ".join(cfg.missing))
        return 1
    for warning in cfg.warnings:
        log.warning(warning)

    now_utc = dt.datetime.now(dt.timezone.utc)
    now_local = now_utc.astimezone(EASTERN)

    if not cfg.skip_time_gate and not in_schedule_window(now_local):
        log.info("outside schedule window (%s local) - exiting", now_local.strftime("%a %H:%M"))
        return 0

    # --- fetch from every enabled source, comparing side by side ---
    all_strikes = []
    source_counts = {}
    for name, fetch in enabled_providers(cfg):
        try:
            strikes = enrich(fetch(cfg), cfg)
            source_counts[name] = {"ok": True, "count": len(strikes)}
            all_strikes.extend(strikes)
            log.info("%s: %d strikes within %d km", name, len(strikes), MAX_RANGE_KM)
        except ProviderError as exc:
            source_counts[name] = {"ok": False, "count": 0}
            log.error("%s failed: %s", name, exc)

    write_strikes_json(all_strikes, source_counts, now_utc)

    # --- alert decisions use the primary source, falling back if it's down ---
    primary = None
    for name in ("xweather", "glm", "blitzortung"):
        if source_counts.get(name, {}).get("ok"):
            primary = name
            break
    if primary is None:
        log.error("no source available; nothing to alert on")
        return 1
    if primary != "xweather":
        log.warning("primary source unavailable, deciding alerts from %s", primary)
    primary_strikes = [s for s in all_strikes if s.source == primary]

    state = state_mod.load()
    sweet = in_zone(primary_strikes, SWEET_SPOT)
    wide = in_zone(primary_strikes, WIDE_ZONE)

    if sweet:
        if state_mod.cooldown_active(state, "sweet", cfg.sweet_cooldown_min, now_utc):
            log.info("sweet-spot strikes present but alert is in cooldown")
        else:
            msg = alerting.format_alert("sweet", summarize(sweet, primary_strikes),
                                        source_counts, cfg, now_utc, now_local)
            if alerting.send_telegram(cfg, msg):
                state_mod.mark_sent(state, "sweet", now_utc)
                log.info("sweet-spot alert sent (%d strikes)", len(sweet))
    elif len(wide) >= cfg.approach_min_strikes:
        if state_mod.cooldown_active(state, "approach", cfg.approach_cooldown_min, now_utc):
            log.info("wide-zone activity but approach alert is in cooldown")
        else:
            msg = alerting.format_alert("approach", summarize(wide, primary_strikes),
                                        source_counts, cfg, now_utc, now_local)
            if alerting.send_telegram(cfg, msg):
                state_mod.mark_sent(state, "approach", now_utc)
                log.info("approach alert sent (%d strikes)", len(wide))
    else:
        log.info("no alert: %d sweet-spot, %d wide-zone strikes (%s)",
                 len(sweet), len(wide), primary)

    state_mod.save(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())

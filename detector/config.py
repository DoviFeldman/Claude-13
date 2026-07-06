"""Configuration from environment variables (GitHub Actions Secrets in CI).

Nothing sensitive lives in the repo: the target coordinate, API keys, and
Telegram credentials all arrive via the environment.
"""

import os
from dataclasses import dataclass, field


def _env_bool(name, default):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # Target coordinate (secret) - the beach/coast point alerts are measured from.
    target_lat: float = 0.0
    target_lon: float = 0.0

    # Xweather (primary source)
    xweather_client_id: str = ""
    xweather_client_secret: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Source toggles - flip these to compare how each network sees the same storm.
    enable_xweather: bool = True
    enable_glm: bool = True
    enable_blitzortung: bool = True

    # Behaviour
    lookback_minutes: int = 10       # strike recency window per run
    max_range_km: float = 250.0
    sweet_cooldown_min: int = 30     # min gap between sweet-spot alerts
    approach_cooldown_min: int = 60  # min gap between wide-zone approach alerts
    approach_min_strikes: int = 5    # wide-zone strikes needed to call it "approaching"
    map_url: str = ""                # public URL of the PWA, included in alerts
    skip_time_gate: bool = False     # manual runs can bypass the schedule window
    dry_run: bool = False            # log the alert instead of sending it

    missing: list = field(default_factory=list)

    @classmethod
    def from_env(cls):
        cfg = cls()
        cfg.missing = []

        lat, lon = os.environ.get("TARGET_LAT"), os.environ.get("TARGET_LON")
        if lat and lon:
            cfg.target_lat, cfg.target_lon = float(lat), float(lon)
        else:
            cfg.missing.append("TARGET_LAT/TARGET_LON")

        cfg.xweather_client_id = os.environ.get("XWEATHER_CLIENT_ID", "")
        cfg.xweather_client_secret = os.environ.get("XWEATHER_CLIENT_SECRET", "")
        if not (cfg.xweather_client_id and cfg.xweather_client_secret):
            cfg.missing.append("XWEATHER_CLIENT_ID/XWEATHER_CLIENT_SECRET")

        cfg.telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        cfg.telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not (cfg.telegram_bot_token and cfg.telegram_chat_id):
            cfg.missing.append("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID")

        cfg.enable_xweather = _env_bool("ENABLE_XWEATHER", True)
        cfg.enable_glm = _env_bool("ENABLE_GLM", True)
        cfg.enable_blitzortung = _env_bool("ENABLE_BLITZORTUNG", True)

        cfg.lookback_minutes = int(os.environ.get("LOOKBACK_MINUTES", "10"))
        cfg.map_url = os.environ.get("MAP_URL", "")
        cfg.skip_time_gate = _env_bool("SKIP_TIME_GATE", False)
        cfg.dry_run = _env_bool("DRY_RUN", False)
        return cfg

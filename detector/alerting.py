"""Telegram alerts - the only notification channel."""

import logging

import requests

log = logging.getLogger(__name__)


def send_telegram(cfg, text):
    """Send a message via the Bot API. Returns True on success."""
    if not cfg.telegram_configured:
        log.info("telegram not configured - alert suppressed:\n%s", text)
        return False
    if cfg.dry_run:
        log.info("DRY RUN - would send Telegram message:\n%s", text)
        return True
    url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": cfg.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=20)
        body = resp.json()
        if not body.get("ok"):
            log.error("telegram send failed: %s", body)
            return False
        return True
    except requests.RequestException as exc:
        log.error("telegram request failed: %s", exc)
        return False


def format_alert(kind, summary, source_counts, cfg, now_utc, now_local):
    """Build the alert message.

    kind: "sweet" (30-60 km trigger) or "approach" (wide-zone warning)
    summary: dict from detector.summarize() for the triggering zone
    """
    if kind == "sweet":
        head = "⚡ <b>LIGHTNING — SWEET SPOT (30–60 km offshore)</b>"
        tail = "Silent full bolts likely. Grab the camera."
    else:
        head = "🌩 <b>Storm in the wider area (60–250 km)</b>"
        tail = "Not in range yet — watch the map for movement toward the coast."

    lines = [head, ""]
    lines.append(
        f"<b>{summary['count']}</b> strikes | closest <b>{summary['min_km']:.0f} km</b> "
        f"{summary['closest_compass']} ({summary['closest_bearing']:.0f}°) | "
        f"median {summary['median_km']:.0f} km"
    )
    lines.append(f"Band of closest strike: <b>{summary['closest_band']}</b>")

    if summary.get("danger_count"):
        lines.append(
            f"⚠️ <b>{summary['danger_count']} strikes inside 30 km</b> — "
            "bolts from the blue reach ~25 km. Not safe on the beach."
        )

    lines.append("")
    lines.append("Per source (last {} min):".format(cfg.lookback_minutes))
    for name, info in source_counts.items():
        if info["ok"]:
            note = " (25s live sample)" if name == "blitzortung" else ""
            lines.append(f"  • {name}: {info['count']} strikes{note}")
        else:
            lines.append(f"  • {name}: unavailable")

    lines.append("")
    lines.append(f"{now_local:%a %I:%M %p %Z} ({now_utc:%H:%M} UTC)")
    if cfg.map_url:
        lines.append(f'<a href="{cfg.map_url}">Open the storm map</a>')
    lines.append(tail)
    return "\n".join(lines)

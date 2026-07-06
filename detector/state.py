"""Alert cooldown state, persisted between runs.

The GitHub Actions workflow commits this file (data/state.json) back to the
repo after each run, so a storm doesn't page you every 5 minutes.
"""

import datetime as dt
import json
import pathlib

STATE_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "state.json"


def load():
    try:
        return json.loads(STATE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def cooldown_active(state, key, minutes, now):
    """True if an alert of this kind fired within the last `minutes`."""
    last = state.get(key)
    if not last:
        return False
    try:
        last_time = dt.datetime.fromisoformat(last)
    except ValueError:
        return False
    return (now - last_time) < dt.timedelta(minutes=minutes)


def mark_sent(state, key, now):
    state[key] = now.isoformat()

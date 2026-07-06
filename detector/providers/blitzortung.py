"""Blitzortung.org - free crowd-sourced lightning network (EXPERIMENTAL).

Blitzortung has no official public API. This taps the same WebSocket feed
LightningMaps.org uses: connect, send a magic handshake, and decode each
message with Blitzortung's LZW-style string compression. Because it's a
live feed (not a history query), a cron run can only sample it - we listen
for `SAMPLE_SECONDS` and report what arrived in that window.

Caveats, by design of the source:
  * unofficial feed; endpoints/format can change without notice
  * sample window means counts are NOT comparable 1:1 with the other
    sources' 10-minute lookback - treat it as "is the network seeing
    this storm too?", not as an absolute count
  * ground-network coverage far offshore is weaker than satellite

Fails soft: any error just drops this source from the comparison.
"""

import json
import logging
import time

from .base import Strike, ProviderError

log = logging.getLogger(__name__)

HOSTS = ["wss://ws1.blitzortung.org", "wss://ws7.blitzortung.org", "wss://ws8.blitzortung.org"]
HANDSHAKE = '{"a": 111}'
SAMPLE_SECONDS = 25


def _lzw_decode(data):
    """Blitzortung's LZW variant (port of the reference JS decoder)."""
    if not data:
        return ""
    table = {}
    prev = data[0]
    result = [prev]
    current = prev
    code = 256
    for ch in data[1:]:
        code_point = ord(ch)
        if code_point < 256:
            entry = ch
        elif code_point in table:
            entry = table[code_point]
        else:
            entry = current + prev  # code not yet in table: KwK case
        result.append(entry)
        prev = entry[0]
        table[code] = current + prev
        code += 1
        current = entry
    return "".join(result)


def fetch(cfg):
    try:
        from websockets.sync.client import connect
    except ImportError as exc:
        raise ProviderError("blitzortung: websockets not installed") from exc

    last_error = None
    for host in HOSTS:
        try:
            return _sample(connect, host)
        except Exception as exc:
            last_error = exc
            log.warning("blitzortung: %s failed: %s", host, exc)
    raise ProviderError(f"blitzortung: all hosts failed: {last_error}")


def _sample(connect, host):
    strikes = []
    deadline = time.monotonic() + SAMPLE_SECONDS
    with connect(host, open_timeout=10, close_timeout=5) as ws:
        ws.send(HANDSHAKE)
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                raw = ws.recv(timeout=max(0.5, remaining))
            except TimeoutError:
                break
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            try:
                msg = json.loads(_lzw_decode(raw))
            except (json.JSONDecodeError, IndexError):
                continue
            lat, lon = msg.get("lat"), msg.get("lon")
            if lat is None or lon is None:
                continue
            # "time" is nanoseconds since epoch
            t = msg.get("time")
            iso = ""
            if isinstance(t, (int, float)) and t > 0:
                iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t / 1e9))
            strikes.append(Strike(lat=float(lat), lon=float(lon), time_utc=iso,
                                  source="blitzortung"))
    log.info("blitzortung: sampled %d strikes in %ds window", len(strikes), SAMPLE_SECONDS)
    return strikes

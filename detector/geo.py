"""Geodesy helpers: haversine distance, bearing, and distance-band classification."""

import math

EARTH_RADIUS_KM = 6371.0088

# Distance bands (km) for lightning over the ocean, from the field guide:
#   0-5     you're in it - rain, wind, danger
#   5-15    rain possible, loud thunder, still real strike risk
#   15-30   usually dry, faint thunder - but "bolts from the blue" reach ~25 km
#   30-60   the photographer sweet spot - full bolts cloud-to-sea, silent, no rain
#   60-150  still see actual bolt channels, pure silent light show
#   150-250 only flashes lighting up cloud tops ("heat lightning" look)
#   250+    too far
BANDS = [
    (0, 5, "IN IT", "danger"),
    (5, 15, "TOO CLOSE", "danger"),
    (15, 30, "CAUTION", "caution"),
    (30, 60, "SWEET SPOT", "sweet"),
    (60, 150, "VISIBLE BOLTS", "visible"),
    (150, 250, "CLOUD FLASHES", "far"),
]

SWEET_SPOT = (30.0, 60.0)
WIDE_ZONE = (60.0, 250.0)
DANGER_LIMIT = 30.0  # inside this, bolts from the blue are a real risk
MAX_RANGE_KM = 250.0

COMPASS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points, in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def initial_bearing_deg(lat1, lon1, lat2, lon2):
    """Initial bearing from point 1 to point 2, degrees clockwise from true north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    y = math.sin(dlmb) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlmb)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def compass_point(bearing_deg):
    """16-point compass label for a bearing."""
    return COMPASS[int((bearing_deg + 11.25) // 22.5) % 16]


def classify_band(distance_km):
    """Return (label, severity) for a distance, or None beyond max range."""
    for lo, hi, label, severity in BANDS:
        if lo <= distance_km < hi:
            return label, severity
    return None

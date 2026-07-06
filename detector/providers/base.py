"""Common strike model shared by all lightning data providers."""

from dataclasses import dataclass


@dataclass
class Strike:
    lat: float
    lon: float
    time_utc: str        # ISO-8601 UTC timestamp of the strike
    source: str          # "xweather" | "glm" | "blitzortung"
    # Filled in by the detector relative to the target coordinate:
    distance_km: float = 0.0
    bearing_deg: float = 0.0
    band: str = ""
    severity: str = ""

    def to_public_dict(self):
        """Serialization for the map site - strike positions are public data."""
        return {
            "lat": round(self.lat, 4),
            "lon": round(self.lon, 4),
            "t": self.time_utc,
            "src": self.source,
            "km": round(self.distance_km, 1),
            "brg": round(self.bearing_deg),
            "band": self.band,
            "sev": self.severity,
        }


class ProviderError(Exception):
    """A provider failed; the detector logs it and continues with the others."""

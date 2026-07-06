"""NOAA GOES-East GLM (Geostationary Lightning Mapper) - free satellite source.

Reads GLM-L2-LCFA flash data from NOAA's open S3 bucket (anonymous access,
no key needed). GOES-East (currently GOES-19) watches the western Atlantic,
so offshore coverage for the US East Coast is strong. Files land every 20
seconds; we read the last `lookback_minutes` worth and extract flash
centroids.

Satellite flashes are cloud-level optical detections (~few km location
accuracy) - great for "is there a storm out there", less precise than
ground networks for exact strike points.
"""

import datetime as dt
import logging
import os
import tempfile

from .base import Strike, ProviderError

log = logging.getLogger(__name__)

BUCKET = os.environ.get("GLM_BUCKET", "noaa-goes19")  # GOES-East
PRODUCT = "GLM-L2-LCFA"
MAX_FILES = 24  # cap S3 downloads per run (~8 min of data at 20s/file)


def _s3_client():
    try:
        import boto3
        from botocore import UNSIGNED
        from botocore.config import Config as BotoConfig
    except ImportError as exc:
        raise ProviderError("glm: boto3 not installed") from exc
    return boto3.client("s3", config=BotoConfig(signature_version=UNSIGNED))


def _hour_prefixes(now, lookback_minutes):
    """S3 prefixes (year/day-of-year/hour) covering the lookback window."""
    prefixes = []
    t = now - dt.timedelta(minutes=lookback_minutes)
    while t <= now:
        prefixes.append(f"{PRODUCT}/{t.year}/{t.timetuple().tm_yday:03d}/{t.hour:02d}/")
        t += dt.timedelta(hours=1)
    end = f"{PRODUCT}/{now.year}/{now.timetuple().tm_yday:03d}/{now.hour:02d}/"
    if end not in prefixes:
        prefixes.append(end)
    return prefixes


def _parse_start_time(key):
    """Parse the sYYYYJJJHHMMSSt start stamp out of an LCFA object key."""
    try:
        stamp = key.split("_s")[1][:13]  # YYYYJJJHHMMSS
        return dt.datetime.strptime(stamp, "%Y%j%H%M%S").replace(tzinfo=dt.timezone.utc)
    except (IndexError, ValueError):
        return None


def fetch(cfg):
    try:
        import netCDF4
    except ImportError as exc:
        raise ProviderError("glm: netCDF4 not installed") from exc

    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(minutes=cfg.lookback_minutes)
    s3 = _s3_client()

    keys = []
    try:
        for prefix in _hour_prefixes(now, cfg.lookback_minutes):
            resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
            for obj in resp.get("Contents", []):
                t = _parse_start_time(obj["Key"])
                if t and t >= cutoff:
                    keys.append((t, obj["Key"]))
    except Exception as exc:  # botocore raises many types; treat all as provider failure
        raise ProviderError(f"glm: S3 listing failed: {exc}") from exc

    keys.sort()
    keys = keys[-MAX_FILES:]
    if not keys:
        log.info("glm: no LCFA files in window (bucket=%s)", BUCKET)
        return []

    strikes = []
    for file_time, key in keys:
        try:
            with tempfile.NamedTemporaryFile(suffix=".nc") as tmp:
                s3.download_fileobj(BUCKET, key, tmp)
                tmp.flush()
                ds = netCDF4.Dataset(tmp.name)
                try:
                    lats = ds.variables["flash_lat"][:]
                    lons = ds.variables["flash_lon"][:]
                    for lat, lon in zip(lats, lons):
                        strikes.append(Strike(
                            lat=float(lat),
                            lon=float(lon),
                            time_utc=file_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            source="glm",
                        ))
                finally:
                    ds.close()
        except Exception as exc:
            log.warning("glm: failed to read %s: %s", key, exc)
    return strikes

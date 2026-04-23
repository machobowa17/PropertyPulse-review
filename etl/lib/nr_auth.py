"""
Shared National Rail Open Data authentication and feed download.

All ETL consumers that need NR API access import from here instead of
duplicating auth logic.  Credentials come from NR_EMAIL / NR_PASSWORD
environment variables.
"""

import json
import logging
import os
import ssl
import urllib.request

logger = logging.getLogger(__name__)

_NR_EMAIL = os.environ.get("NR_EMAIL", "")
_NR_PASSWORD = os.environ.get("NR_PASSWORD", "")

_NR_AUTH_URL = "https://opendata.nationalrail.co.uk/authenticate"
_NR_FARES_URL = "https://opendata.nationalrail.co.uk/api/staticfeeds/2.0/fares"


def nr_authenticate() -> str:
    """Authenticate with NR Open Data portal. Returns X-Auth-Token.

    Raises RuntimeError if NR_EMAIL / NR_PASSWORD env vars are not set.
    """
    if not _NR_EMAIL or not _NR_PASSWORD:
        raise RuntimeError(
            "NR_EMAIL and NR_PASSWORD env vars must be set for NR API access"
        )
    ctx = ssl._create_unverified_context()
    payload = json.dumps({"username": _NR_EMAIL, "password": _NR_PASSWORD}).encode()
    req = urllib.request.Request(
        _NR_AUTH_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        token = json.loads(resp.read())["token"]
    logger.debug("NR auth succeeded")
    return token


def download_feed(url: str, dest_path: str, label: str = "feed") -> str:
    """Download a static feed from NR Open Data portal.

    Args:
        url: Full NR Open Data feed URL.
        dest_path: Local file path to write to.
        label: Human-readable label for log messages.

    Returns:
        dest_path on success.
    """
    ctx = ssl._create_unverified_context()
    token = nr_authenticate()
    logger.info("Downloading %s...", label)
    req = urllib.request.Request(url, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
    size_mb = os.path.getsize(dest_path) / 1024 / 1024
    logger.info("%s saved to %s (%.1f MB)", label, dest_path, size_mb)
    return dest_path


def download_fares(dest_path: str = "/tmp/nr_fares.zip") -> str:
    """Download NR fares ZIP (~46 MB). Returns file path."""
    return download_feed(_NR_FARES_URL, dest_path, "fares (~46 MB)")

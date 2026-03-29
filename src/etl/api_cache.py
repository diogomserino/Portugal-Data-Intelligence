"""
Portugal Data Intelligence — API Response Cache
=================================================
Simple disk-based cache for API responses to avoid redundant HTTP calls.

Each cached response is stored as a JSON file with metadata (URL, timestamp,
TTL). Stale entries are automatically refreshed on next access.

Usage:
    from src.etl.api_cache import CachedSession
    session = CachedSession(ttl_hours=24)
    response = session.get("https://api.example.com/data")
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

import requests

from config.settings import PROJECT_ROOT
from src.utils.logger import get_logger

logger = get_logger(__name__)

CACHE_DIR = PROJECT_ROOT / ".api_cache"


class CachedSession:
    """A requests-compatible session with transparent disk caching.

    Parameters
    ----------
    ttl_hours : float
        Time-to-live for cached responses in hours. Default: 24.
    cache_dir : Path, optional
        Directory for cache files. Default: ``<project>/.api_cache/``.
    enabled : bool
        Set to False to bypass caching entirely.
    """

    def __init__(
        self,
        ttl_hours: float = 24.0,
        cache_dir: Optional[Path] = None,
        enabled: bool = True,
    ):
        self.ttl_seconds = ttl_hours * 3600
        self.cache_dir = cache_dir or CACHE_DIR
        self.enabled = enabled
        self._session = requests.Session()

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(
                "API cache enabled — dir: %s, TTL: %.1f hours",
                self.cache_dir,
                ttl_hours,
            )

    def _cache_key(self, url: str, params: Optional[dict] = None) -> str:
        """Generate a deterministic cache key from URL and parameters."""
        key_str = url
        if params:
            key_str += "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> Optional[dict]:
        """Read a cached response if it exists and is not expired."""
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            age = time.time() - entry.get("cached_at", 0)
            if age > self.ttl_seconds:
                logger.debug("Cache expired for key %s (age: %.0fs)", key, age)
                return None
            logger.debug("Cache hit for key %s (age: %.0fs)", key, age)
            return entry
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read cache entry %s: %s", key, exc)
            return None

    def _write_cache(self, key: str, url: str, text: str, status_code: int):
        """Write a response to the cache."""
        entry = {
            "url": url,
            "status_code": status_code,
            "text": text,
            "cached_at": time.time(),
        }
        try:
            path = self._cache_path(key)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            logger.debug("Cached response for %s -> %s", url[:80], path.name)
        except OSError as exc:
            logger.warning("Failed to write cache: %s", exc)

    def get(
        self,
        url: str,
        params: Optional[dict] = None,
        timeout: int = 30,
        **kwargs,
    ) -> requests.Response:
        """Send a GET request with transparent caching.

        Parameters
        ----------
        url : str
            The URL to fetch.
        params : dict, optional
            Query parameters.
        timeout : int
            Request timeout in seconds.

        Returns
        -------
        requests.Response
            Either a cached or fresh response.
        """
        if self.enabled:
            key = self._cache_key(url, params)
            cached = self._read_cache(key)
            if cached is not None:
                # Build a Response object from cache using public attributes
                resp = requests.Response()
                resp.status_code = cached["status_code"]
                resp._content = cached["text"].encode("utf-8")  # noqa: SLF001
                resp.encoding = "utf-8"
                resp.url = cached.get("url", url)
                resp.headers["Content-Type"] = "application/json; charset=utf-8"
                return resp

        # Fetch from network
        resp = self._session.get(url, params=params, timeout=timeout, **kwargs)

        if self.enabled and resp.status_code == 200:
            key = self._cache_key(url, params)
            self._write_cache(key, url, resp.text, resp.status_code)

        return resp

    def clear_cache(self):
        """Remove all cached files."""
        if not self.cache_dir.exists():
            return
        count = 0
        for path in self.cache_dir.glob("*.json"):
            path.unlink()
            count += 1
        logger.info("Cleared %d cached API responses.", count)

    def cache_stats(self) -> dict:
        """Return cache statistics."""
        if not self.cache_dir.exists():
            return {"entries": 0, "size_kb": 0}
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)
        return {
            "entries": len(files),
            "size_kb": round(total_size / 1024, 1),
        }

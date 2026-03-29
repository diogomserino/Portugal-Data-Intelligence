"""
Tests for the API response cache (src/etl/api_cache.py).
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.etl.api_cache import CachedSession


@pytest.fixture
def cache_dir(tmp_path):
    """Provide an isolated cache directory."""
    return tmp_path / "test_cache"


@pytest.fixture
def session(cache_dir):
    """Create a CachedSession with short TTL for testing."""
    return CachedSession(ttl_hours=0.001, cache_dir=cache_dir, enabled=True)


class TestCachedSession:
    """Tests for the CachedSession class."""

    def test_cache_dir_created(self, session, cache_dir):
        """Cache directory should be created on init."""
        assert cache_dir.exists()

    def test_cache_key_deterministic(self, session):
        """Same URL should produce the same cache key."""
        key1 = session._cache_key("https://example.com/data")
        key2 = session._cache_key("https://example.com/data")
        assert key1 == key2

    def test_cache_key_different_for_different_urls(self, session):
        """Different URLs should produce different keys."""
        key1 = session._cache_key("https://example.com/a")
        key2 = session._cache_key("https://example.com/b")
        assert key1 != key2

    def test_cache_key_includes_params(self, session):
        """Cache key should differ when params differ."""
        key1 = session._cache_key("https://example.com", {"a": "1"})
        key2 = session._cache_key("https://example.com", {"a": "2"})
        assert key1 != key2

    def test_write_and_read_cache(self, session):
        """Should be able to write and read back a cached entry."""
        session._write_cache("testkey", "https://example.com", '{"data": 1}', 200)
        entry = session._read_cache("testkey")
        assert entry is not None
        assert entry["url"] == "https://example.com"
        assert entry["text"] == '{"data": 1}'
        assert entry["status_code"] == 200

    def test_expired_cache_returns_none(self, session):
        """Expired entries should return None."""
        session._write_cache("testkey", "https://example.com", "data", 200)
        # Force expiry by setting TTL to 0
        session.ttl_seconds = 0
        entry = session._read_cache("testkey")
        assert entry is None

    def test_clear_cache(self, session):
        """clear_cache should remove all cached files."""
        session._write_cache("key1", "url1", "data1", 200)
        session._write_cache("key2", "url2", "data2", 200)
        assert session.cache_stats()["entries"] == 2
        session.clear_cache()
        assert session.cache_stats()["entries"] == 0

    def test_cache_stats(self, session):
        """cache_stats should report correct entry count."""
        assert session.cache_stats()["entries"] == 0
        session._write_cache("key1", "url1", "data1", 200)
        stats = session.cache_stats()
        assert stats["entries"] == 1
        assert stats["size_kb"] > 0

    def test_disabled_cache(self, cache_dir):
        """When disabled, caching should be bypassed."""
        session = CachedSession(enabled=False, cache_dir=cache_dir)
        session._write_cache("key", "url", "data", 200)
        # Cache dir may not even exist
        assert not cache_dir.exists() or session.cache_stats()["entries"] == 0

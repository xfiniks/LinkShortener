import pytest
import json
from datetime import datetime, timezone, timedelta
from app.cache import (
    get_url_cache_key, get_cached_url, cache_url, invalidate_url_cache,
    increment_access_counter, add_popular_url, is_popular_url, 
    get_links_to_sync, get_buffered_clicks, get_buffered_last_access,
    reset_buffered_stats, add_click_details, get_and_clear_click_details
)

def test_get_url_cache_key():
    assert get_url_cache_key("abc123") == "url:abc123"

def test_get_cached_url(redis_mock):
    # Set up test data
    redis_mock.set("url:abc123", "https://example.com")
    
    # Test cache hit
    assert get_cached_url("abc123") == "https://example.com"
    
    # Test cache miss
    assert get_cached_url("nonexistent") is None

def test_cache_url(redis_mock):
    # Test without expiry
    cache_url("abc123", "https://example.com")
    assert redis_mock.get("url:abc123") == "https://example.com"
    
    # Test with expiry
    cache_url("def456", "https://example.org", expire=60)
    assert redis_mock.get("url:def456") == "https://example.org"
    # Check TTL is set
    assert redis_mock.ttl("url:def456") > 0

def test_invalidate_url_cache(redis_mock):
    # Set up test data
    redis_mock.set("url:abc123", "https://example.com")
    
    # Test invalidation
    invalidate_url_cache("abc123")
    assert redis_mock.get("url:abc123") is None

def test_add_popular_url(redis_mock):
    add_popular_url("abc123")
    assert redis_mock.sismember("popular_urls", "abc123")

def test_is_popular_url(redis_mock):
    # Test non-popular URL
    assert not is_popular_url("abc123")
    
    # Test popular URL
    redis_mock.sadd("popular_urls", "abc123")
    assert is_popular_url("abc123")

def test_increment_access_counter(redis_mock):
    # First increment
    count = increment_access_counter("abc123")
    assert count == 1
    
    # Second increment
    count = increment_access_counter("abc123")
    assert count == 2
    
    # Check last access was set
    assert redis_mock.exists("last_access:abc123")
    
    # Check link is marked for sync
    assert redis_mock.sismember("links_to_sync", "abc123")

def test_get_links_to_sync(redis_mock):
    # Empty set initially
    assert get_links_to_sync() == set()
    
    # Add links to sync
    redis_mock.sadd("links_to_sync", "abc123")
    redis_mock.sadd("links_to_sync", "def456")
    
    # Check links are returned
    assert get_links_to_sync() == {"abc123", "def456"}

def test_get_buffered_clicks(redis_mock):
    # No clicks initially
    assert get_buffered_clicks("abc123") == 0
    
    # Set clicks
    redis_mock.set("clicks:abc123", "5")
    assert get_buffered_clicks("abc123") == 5

def test_get_buffered_last_access(redis_mock):
    # No last access initially
    assert get_buffered_last_access("abc123") is None
    
    # Set last access
    now = datetime.now(timezone.utc)
    redis_mock.set("last_access:abc123", now.isoformat())
    
    # Get last access
    last_access = get_buffered_last_access("abc123")
    assert isinstance(last_access, datetime)
    assert last_access.tzinfo is not None

def test_reset_buffered_stats(redis_mock):
    # Set up test data
    redis_mock.set("clicks:abc123", "5")
    redis_mock.set("last_access:abc123", datetime.now(timezone.utc).isoformat())
    redis_mock.sadd("links_to_sync", "abc123")
    
    # Reset stats
    reset_buffered_stats("abc123")
    
    # Check all keys are removed
    assert not redis_mock.exists("clicks:abc123")
    assert not redis_mock.exists("last_access:abc123")
    assert not redis_mock.sismember("links_to_sync", "abc123")

def test_add_click_details(redis_mock):
    client_info = {
        "ip_address": "192.168.1.1",
        "user_agent": "Test Browser",
        "referer": "https://example.com"
    }
    
    # Add click details
    add_click_details("abc123", client_info)
    
    # Check details were added to the list
    assert redis_mock.llen("click_details:abc123") == 1

def test_get_and_clear_click_details(redis_mock):
    # Add some click details
    for i in range(3):
        click_data = {
            "short_code": "abc123",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip_address": f"192.168.1.{i}",
            "user_agent": "Test Browser",
            "referer": "https://example.com"
        }
        redis_mock.lpush("click_details:abc123", json.dumps(click_data))
    
    # Get and clear details
    details = get_and_clear_click_details("abc123")
    
    # Should have 3 details
    assert len(details) == 3
    
    # List should be empty now
    assert redis_mock.llen("click_details:abc123") == 0
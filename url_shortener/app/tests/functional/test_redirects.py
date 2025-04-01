import pytest
from fastapi import status
from datetime import datetime, timedelta, timezone
from app.models import Link
from app.cache import cache_url, get_cached_url, get_buffered_clicks, increment_access_counter
import time
from unittest.mock import patch

def test_redirect_to_url(client, db):
    response = client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/redirect-test"}
    )

    short_code = response.json()["short_code"]

    response = client.get(f"/{short_code}", follow_redirects=False)
    
    assert response.status_code in [301, 302, 307, 308]
    assert response.headers["location"] == "https://example.com/redirect-test"
    
    link = db.query(Link).filter(Link.short_code == short_code).first()
    assert link.click_count >= 1

def test_redirect_with_caching(client, db, redis_mock):
    original_url = "https://example.com/cache-test"
    response = client.post(
        "/links/shorten",
        json={"original_url": original_url}
    )
    short_code = response.json()["short_code"]
    
    cache_url(short_code, original_url)
    
    assert get_cached_url(short_code) == original_url
    
    with patch('app.routers.links.get_cached_url', wraps=get_cached_url) as mock_get_cached:
        response = client.get(f"/{short_code}", follow_redirects=False)
        
        mock_get_cached.assert_called_with(short_code)
    
    clicks = get_buffered_clicks(short_code)
    assert clicks >= 1

def test_redirect_expired_link(client, auth_client, db):
    expiry_time = datetime.now(timezone.utc) + timedelta(seconds=1)
    response = auth_client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/expiring",
            "expires_at": expiry_time.isoformat()
        }
    )
    short_code = response.json()["short_code"]
    
    response = client.get(f"/{short_code}", follow_redirects=False)
    assert response.status_code in [301, 302, 307, 308]
    
    time.sleep(2)
    
    response = client.get(f"/{short_code}", follow_redirects=False)
    
    assert response.status_code in [404, 410]
    
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if link:
        now = datetime.now(timezone.utc)
        link_expires_at = link.expires_at.replace(tzinfo=timezone.utc) if link.expires_at.tzinfo is None else link.expires_at
        assert now > link_expires_at
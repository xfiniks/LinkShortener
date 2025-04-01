import pytest
from datetime import datetime, timedelta, timezone
from fastapi import status
from app.models import Click, Link

def test_create_short_link(auth_client):
    # Test creating a link with auto-generated short code
    response = auth_client.post(
        "/links/shorten",
        json={"original_url": "https://example.com"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "short_code" in data
    assert data["original_url"] == "https://example.com"
    assert "short_url" in data
    assert "created_at" in data
    
    # Test creating a link with custom alias
    response = auth_client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.org",
            "custom_alias": "mylink"
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["short_code"] == "mylink"
    assert data["original_url"] == "https://example.org"
    
    # Test duplicate custom alias
    response = auth_client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.net",
            "custom_alias": "mylink"
        }
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    # Test invalid URL
    response = auth_client.post(
        "/links/shorten",
        json={
            "original_url": "not_a_valid_url",
        }
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_get_link_info(auth_client):
    # Create a link first
    response = auth_client.post(
        "/links/shorten",
        json={"original_url": "https://example.com"}
    )
    short_code = response.json()["short_code"]
    
    # Test getting link info
    response = auth_client.get(f"/links/{short_code}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["short_code"] == short_code
    assert data["original_url"] == "https://example.com"
    
    # Test non-existent link
    response = auth_client.get("/links/nonexistent")
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_search_link(auth_client):
    # Create unique url
    timestamp = datetime.now().timestamp()
    url1 = f"https://search-test-{timestamp}-1.com"
    url2 = f"https://search-test-{timestamp}-2.com"
    url3 = f"https://search-test-{timestamp}-3.com"
    
    # Create links
    response1 = auth_client.post("/links/shorten", json={"original_url": url1})
    assert response1.status_code == 201
    
    response2 = auth_client.post("/links/shorten", json={"original_url": url2})
    assert response2.status_code == 201
    
    response3 = auth_client.post("/links/shorten", json={"original_url": url3})
    assert response3.status_code == 201
    
    # Test search
    response = auth_client.get("/links/search", params={"original_url": url1})
    assert response.status_code == 200
    data = response.json()
    
    # Assert
    assert data["count"] == 1
    assert len(data["links"]) == 1
    assert data["links"][0]["original_url"] == url1
    assert data["links"][0]["short_code"] == response1.json()["short_code"]
    
    # Assert
    non_existent_url = f"https://non-existent-{timestamp}.com"
    response = auth_client.get("/links/search", params={"original_url": non_existent_url})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert len(data["links"]) == 0

def test_update_link(auth_client):
    # Create a link first
    response = auth_client.post(
        "/links/shorten",
        json={"original_url": "https://example.com"}
    )
    short_code = response.json()["short_code"]
    
    # Test updating link
    response = auth_client.put(
        f"/links/{short_code}",
        json={"original_url": "https://updated-example.com"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["short_code"] == short_code
    assert data["original_url"] == "https://updated-example.com"

def test_delete_link(auth_client):
    # Create a link first
    response = auth_client.post(
        "/links/shorten",
        json={"original_url": "https://example.com"}
    )
    short_code = response.json()["short_code"]
    
    # Test deleting link
    response = auth_client.delete(f"/links/{short_code}")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verify deletion
    response = auth_client.get(f"/links/{short_code}")
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_get_link_stats(auth_client, db):
    # Create link
    timestamp = datetime.now().timestamp()
    test_url = f"https://stats-test-{timestamp}.com"
    
    response = auth_client.post(
        "/links/shorten",
        json={"original_url": test_url}
    )
    assert response.status_code == 201
    short_code = response.json()["short_code"]
    
    # Get link from db
    link = db.query(Link).filter(Link.short_code == short_code).first()
    
    # Update click count
    link.click_count = 3
    link.last_accessed = datetime.now(timezone.utc)
    
    # Create clicks
    for i in range(3):
        click = Click(
            link_id=link.id,
            ip_address=f"192.168.1.{i}",
            user_agent="Test Browser",
            referer="https://test.com"
        )
        db.add(click)
    
    db.commit()
    
    # Check stats
    response = auth_client.get(f"/links/{short_code}/stats")
    assert response.status_code == 200
    stats = response.json()
    
    assert stats["short_code"] == short_code
    assert stats["original_url"] == test_url
    assert stats["click_count"] == 3
    assert "last_accessed" in stats
    assert "recent_clicks" in stats
    assert len(stats["recent_clicks"]) > 0
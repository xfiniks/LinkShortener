import pytest
from fastapi import HTTPException
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from jose import JWTError

from app.dependencies import get_current_user, get_current_active_user, get_link_owner_or_admin, get_client_info
from app.models import User, Link

@pytest.mark.asyncio
async def test_get_current_user_valid_token():
    token_data = {"sub": "testuser", "user_id": 1}
    with patch('app.dependencies.jwt.decode', return_value=token_data):

        mock_db = MagicMock()
        mock_user = User(id=1, username="testuser", email="test@example.com")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        user = await get_current_user("valid_token", mock_db)
        assert user == mock_user

@pytest.mark.asyncio
async def test_get_current_user_invalid_token():
    with patch('app.dependencies.jwt.decode', side_effect=JWTError("Invalid token")):
        mock_db = MagicMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid_token", mock_db)
        
        assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_get_current_active_user():
    active_user = User(id=1, username="active", email="active@example.com", is_active=True)
    result = await get_current_active_user(active_user)
    assert result == active_user
    
    inactive_user = User(id=2, username="inactive", email="inactive@example.com", is_active=False)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(inactive_user)
    assert exc_info.value.status_code == 403
    
    result = await get_current_active_user(None)
    assert result is None

@pytest.mark.asyncio
async def test_get_link_owner_or_admin():
    owner = User(id=1, username="owner", email="owner@example.com")
    
    link = Link(id=1, short_code="abc123", original_url="https://example.com", owner_id=1)
    
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = link
    
    result = await get_link_owner_or_admin("abc123", owner, mock_db)
    assert result == link
    
    other_user = User(id=2, username="other", email="other@example.com")
    with pytest.raises(HTTPException) as exc_info:
        await get_link_owner_or_admin("abc123", other_user, mock_db)
    assert exc_info.value.status_code == 403
    
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await get_link_owner_or_admin("nonexistent", owner, mock_db)
    assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_get_client_info():
    mock_request = MagicMock()
    mock_request.client.host = "192.168.1.1"
    mock_request.headers = {
        "user-agent": "Test Browser",
        "referer": "https://example.com"
    }
    
    client_info = await get_client_info(mock_request)
    
    assert client_info["ip_address"] == "192.168.1.1"
    assert client_info["user_agent"] == "Test Browser"
    assert client_info["referer"] == "https://example.com"
    assert isinstance(client_info["timestamp"], datetime)
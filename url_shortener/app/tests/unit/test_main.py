import pytest
import asyncio
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app, lifespan, periodically_cleanup_expired_links, root
from app.database import SessionLocal
from app.models import Link

@pytest.mark.asyncio
async def test_lifespan():    
    # Create app mock
    mock_app = MagicMock()
    mock_app.state = MagicMock()
    
    # Create db mock
    mock_db = MagicMock()
    
    with patch('app.main.SessionLocal', return_value=mock_db):
        with patch('asyncio.create_task') as mock_create_task:
            async with lifespan(mock_app) as _:
                assert mock_create_task.call_count == 2
                
                assert hasattr(mock_app.state, 'background_tasks')
                assert len(mock_app.state.background_tasks) == 2
                
    # Check, that db.commit was called once
    mock_db.__enter__.return_value.commit.assert_called_once()

@pytest.mark.asyncio
async def test_cleanup_expired_links():    
    with patch('asyncio.sleep', side_effect=[None, asyncio.CancelledError()]):
        mock_db = MagicMock()
        with patch('app.main.SessionLocal', return_value=mock_db):
            with patch('app.main.invalidate_url_cache') as mock_invalidate:
                with patch('app.main.reset_buffered_stats') as mock_reset:
                    try:
                        await periodically_cleanup_expired_links()
                    except asyncio.CancelledError:
                        pass
                    
                    mock_db.__enter__.assert_called()
                    mock_db.__exit__.assert_called()

@pytest.mark.asyncio
async def test_cleanup_expired_links():
    from app.main import periodically_cleanup_expired_links
    from app.models import Link
    
    # Create test links
    expired_link1 = MagicMock()
    expired_link1.short_code = "abc123"
    expired_link1.id = 1
    
    expired_link2 = MagicMock()
    expired_link2.short_code = "def456"
    expired_link2.id = 2
    
    expired_links = [expired_link1, expired_link2]
    
    # Create db mock
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_filter = MagicMock()
    
    mock_db.__enter__.return_value = mock_db
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_filter
    mock_filter.all.return_value = expired_links
    
    # Mock methods
    with patch('app.main.SessionLocal', return_value=mock_db):
        with patch('app.main.invalidate_url_cache') as mock_invalidate:
            with patch('app.main.reset_buffered_stats') as mock_reset:
                with patch('asyncio.sleep', side_effect=[None, asyncio.CancelledError()]):
                    try:
                        await periodically_cleanup_expired_links()
                    except asyncio.CancelledError:
                        pass
    
    # Asserts
    mock_db.query.assert_called_with(Link)
    
    assert mock_query.filter.called
    
    assert mock_invalidate.call_count == 2
    mock_invalidate.assert_has_calls([
        call("abc123"),
        call("def456")
    ], any_order=True)
    
    assert mock_reset.call_count == 2
    mock_reset.assert_has_calls([
        call("abc123"),
        call("def456")
    ], any_order=True)
    
    assert mock_db.delete.call_count == 2
    mock_db.delete.assert_has_calls([
        call(expired_link1),
        call(expired_link2)
    ], any_order=True)
    
    mock_db.commit.assert_called_once()
    
    mock_db.__enter__.assert_called()
    mock_db.__exit__.assert_called()

@pytest.mark.asyncio
async def test_log_requests_middleware():
    from app.main import log_requests
    
    mock_request = MagicMock()
    mock_request.url.path = "/links/shorten"
    mock_request.method = "POST"
    
    mock_response = MagicMock()
    mock_response.status_code = 201
    
    async def mock_call_next(_):
        return mock_response
    
    with patch('time.time', side_effect=[100.0, 100.5]):
        response = await log_requests(mock_request, mock_call_next)
        
        assert response == mock_response

@pytest.mark.asyncio
async def test_root_endpoint():
    
    result = await root()
    
    assert "message" in result
    assert "docs_url" in result
    assert "version" in result
    assert result["message"] == "URL Shortener API"
    assert result["docs_url"] == "/docs"
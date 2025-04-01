import pytest
from jose import jwt
from datetime import datetime, timedelta, timezone
from app.utils import (
    generate_short_code, verify_password, get_password_hash,
    create_access_token, build_short_url, is_expired, extract_client_info
)
from app.config import settings

def test_generate_short_code():
    # Test default length
    code = generate_short_code()
    assert len(code) == settings.DEFAULT_SHORT_CODE_LENGTH
    assert all(c.isalnum() for c in code)
    
    # Test custom length
    custom_length = 10
    code = generate_short_code(custom_length)
    assert len(code) == custom_length
    
    # Test uniqueness (statistically probable)
    codes = [generate_short_code() for _ in range(50)]
    assert len(set(codes)) == 50  # All should be unique

def test_verify_password():
    # Generate a real password hash for testing
    password = "test_password123"
    hashed = get_password_hash(password)
    
    # Test correct password
    assert verify_password(password, hashed)
    
    # Test incorrect password
    assert not verify_password("wrong_password", hashed)

def test_get_password_hash():
    # Test that hashes are different for the same password
    password = "test_password123"
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)
    
    # Hashes should be different due to salt
    assert hash1 != hash2
    
    # Both hashes should validate with the original password
    assert verify_password(password, hash1)
    assert verify_password(password, hash2)

def test_create_access_token():
    test_data = {"sub": "test", "user_id": 1}
    
    # Test token with default expiry
    token = create_access_token(test_data)
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    assert decoded["sub"] == test_data["sub"]
    assert decoded["user_id"] == test_data["user_id"]
    assert "exp" in decoded
    
    # Test token with custom expiry
    custom_expires = timedelta(minutes=15)
    token = create_access_token(test_data, custom_expires)
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    assert decoded["sub"] == test_data["sub"]
    assert decoded["user_id"] == test_data["user_id"]
    
    token_exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    actual_interval = token_exp_time - now
    assert abs((actual_interval - custom_expires).total_seconds()) < 1

def test_build_short_url():
    short_code = "abc123"
    expected_url = f"{settings.BASE_URL}/{short_code}"
    assert build_short_url(short_code) == expected_url

def test_is_expired():
    # Test with future date
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert not is_expired(future)
    
    # Test with past date
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assert is_expired(past)
    
    # Test with None (no expiry)
    assert not is_expired(None)
    
    # Test with naive datetime
    naive_past = datetime.now() - timedelta(days=1)
    assert is_expired(naive_past)

def test_extract_client_info():
    # Create a mock request with headers
    class MockRequest:
        def __init__(self):
            self.client = type('obj', (object,), {'host': '192.168.1.1'})
            self.headers = {
                "user-agent": "Test Agent",
                "referer": "https://example.com/page"
            }
    
    request = MockRequest()
    info = extract_client_info(request)
    
    assert info["ip_address"] == "192.168.1.1"
    assert info["user_agent"] == "Test Agent"
    assert info["referer"] == "https://example.com/page"
    assert isinstance(info["timestamp"], datetime)
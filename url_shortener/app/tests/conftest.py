import os

os.environ["TESTING"] = "True"

import pytest
import fakeredis
import asyncio
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone

from app.database import Base, get_db, SessionLocal, engine
from app.main import app as fastapi_app
from app.models import User, Link, Click
from app.utils import get_password_hash
from app.dependencies import get_current_active_user, get_link_owner_or_admin, get_client_info
import app.cache
from app.utils import extract_client_info
from fastapi import Request

# Mock Redis client
@pytest.fixture(scope="function")
def redis_mock():
    original_redis = app.cache.redis_client

    fake_redis = fakeredis.FakeStrictRedis(decode_responses=True)

    app.cache.redis_client = fake_redis
    
    yield fake_redis
    
    app.cache.redis_client = original_redis
    
@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

        Base.metadata.drop_all(bind=engine)

async def mock_client_info(request: Request = None):
    return {
        "ip_address": "127.0.0.1",
        "user_agent": "Test Client",
        "referer": "https://test.com",
        "timestamp": datetime.now(timezone.utc)
    }

@pytest.fixture
def client(db, redis_mock):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_client_info] = mock_client_info
    
    with TestClient(fastapi_app) as client:
        yield client
    
    fastapi_app.dependency_overrides = {}

@pytest.fixture
def auth_client(client, db):
    hashed_password = get_password_hash("testpassword")
    test_user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
        is_active=True
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    
    response = client.post(
        "/auth/token",
        data={"username": "testuser", "password": "testpassword"}
    )
    token = response.json()["access_token"]
    
    async def override_get_current_user():
        return test_user
    
    fastapi_app.dependency_overrides[get_current_active_user] = override_get_current_user
    
    async def override_get_link_owner_or_admin(short_code: str):
        link = db.query(Link).filter(Link.short_code == short_code).first()
        if not link:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Link not found"
            )
        
        return link
    
    fastapi_app.dependency_overrides[get_link_owner_or_admin] = override_get_link_owner_or_admin
    
    client.headers = {"Authorization": f"Bearer {token}"}
    return client
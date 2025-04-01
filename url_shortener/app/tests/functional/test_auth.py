import pytest
from fastapi import status

def test_register_user(client):
    # Test successful registration
    response = client.post(
        "/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert "id" in data
    assert "created_at" in data
    
    # Test duplicate username
    response = client.post(
        "/auth/register",
        json={
            "username": "newuser",
            "email": "another@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_login(client, db):
    # Create user for testing
    response = client.post(
        "/auth/register",
        json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Test successful login
    response = client.post(
        "/auth/token",
        data={
            "username": "loginuser",
            "password": "password123"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
    # Test failed login - wrong password
    response = client.post(
        "/auth/token",
        data={
            "username": "loginuser",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Test failed login - non-existent user
    response = client.post(
        "/auth/token",
        data={
            "username": "nonexistentuser",
            "password": "password123"
        }
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
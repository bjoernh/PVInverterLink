"""
Tests for authentication and authorization functionality.
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_with_valid_credentials(client, test_user):
    """Test successful login with valid credentials."""
    response = await client.post("/login", data={"username": "testuser@example.com", "password": "testpassword123"})
    assert response.status_code == 200
    # Check that auth cookie was set
    assert "fastapiusersauth" in response.cookies or "HX-Redirect" in response.headers


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_with_invalid_password(client, test_user):
    """Test login failure with wrong password."""
    response = await client.post("/login", data={"username": "testuser@example.com", "password": "wrongpassword"})
    assert response.status_code == 200
    assert "Username oder Passwort falsch" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_with_nonexistent_user(client):
    """Test login failure with non-existent user."""
    response = await client.post("/login", data={"username": "nonexistent@example.com", "password": "anypassword"})
    assert response.status_code == 200
    assert "Username oder Passwort falsch" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_with_inactive_user(client, db_session):
    """Test login failure with inactive user."""
    from tests.helpers import create_user_in_db

    await create_user_in_db(db_session, email="inactive@example.com", is_active=False)

    response = await client.post("/login", data={"username": "inactive@example.com", "password": "testpassword123"})
    assert response.status_code == 200
    assert "Username oder Passwort falsch" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logout(client, test_user):
    """Test user logout."""
    # First login
    login_response = await client.post(
        "/login", data={"username": "testuser@example.com", "password": "testpassword123"}
    )
    assert login_response.status_code == 200

    # Then logout
    logout_response = await client.get("/logout")
    assert logout_response.status_code in [302, 200]
    assert logout_response.headers.get("location") == "/login" or "HX-Redirect" in logout_response.headers


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logout_without_login(client):
    """Test logout when not logged in."""
    response = await client.get("/logout")
    # Should redirect to login
    assert response.status_code in [302, 303]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bearer_token_login(client, test_user):
    """Test getting a bearer token via JWT endpoint."""
    response = await client.post(
        "/auth/jwt/login", data={"username": "testuser@example.com", "password": "testpassword123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bearer_token_authentication(client, bearer_token):
    """Test accessing protected route with bearer token."""
    response = await client.get("/authenticated-route", headers={"Authorization": f"Bearer {bearer_token}"})
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "testuser@example.com" in data["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_protected_route_without_auth(client):
    """Test accessing protected route without authentication."""
    response = await client.get("/authenticated-route")
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_protected_route_with_invalid_token(client):
    """Test accessing protected route with invalid bearer token."""
    response = await client.get("/authenticated-route", headers={"Authorization": "Bearer invalid-token-12345"})
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_page_requires_auth(client):
    """Test that start page redirects when not authenticated."""
    response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_page_with_auth(client, test_user):
    """Test that authenticated user can access start page."""
    # Login first
    await client.post("/login", data={"username": "testuser@example.com", "password": "testpassword123"})

    # Access start page
    response = await client.get("/")
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_login_page(client):
    """Test GET request to login page."""
    response = await client.get("/login")
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_expired_html_redirect(client):
    """Test that HTML requests to protected routes redirect to login on 401."""
    response = await client.get("/authenticated-route", headers={"Accept": "text/html"})
    # Should redirect to login page
    assert response.status_code == 302  # Found redirect
    assert response.headers["location"] == "/login"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_expired_api_error(client):
    """Test that API requests return helpful error message on 401."""
    response = await client.get("/authenticated-route", headers={"Accept": "application/json"})
    assert response.status_code == 401
    data = response.json()
    assert "message" in data
    assert "Session expired" in data["message"]
    assert "error" in data
    assert data["error"] == "unauthorized"

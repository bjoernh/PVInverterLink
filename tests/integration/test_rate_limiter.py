import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.enable_rate_limiter
async def test_login_rate_limit(client: AsyncClient):
    # Exceed the rate limit
    for _ in range(6):
        response = await client.post("/login", data={"username": "test@example.com", "password": "password"})

    assert response.status_code == 429

@pytest.mark.asyncio
@pytest.mark.enable_rate_limiter
async def test_signup_rate_limit(client: AsyncClient):
    # Exceed the rate limit
    for i in range(6):
        response = await client.post("/signup", data={"first_name": "Test", "last_name": "User", "email": f"test{i}@example.com", "password": "ValidPassword123"})

    assert response.status_code == 429

@pytest.mark.asyncio
@pytest.mark.enable_rate_limiter
async def test_request_reset_password_rate_limit(client: AsyncClient, db_session):
    from tests.helpers import create_user_in_db
    # Create users first
    for i in range(6):
        await create_user_in_db(db_session, email=f"test{i}@example.com")

    # Exceed the rate limit
    for i in range(6):
        response = await client.post("/request_reset_password", headers={"HX-Prompt": f"test{i}@example.com"})

    assert response.status_code == 429
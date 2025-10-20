import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from solar_backend.app import app
from tests.helpers import create_user_in_db, login_user
from solar_backend.db import sessionmanager, get_async_session


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_inverter_creation_with_same_serial():
    """Test that concurrent requests with same serial only create one inverter"""
    async def get_db_override_isolated():
        async with sessionmanager.session() as session:
            yield session

    app.dependency_overrides[get_async_session] = get_db_override_isolated

    async with sessionmanager.session() as session:
        user = await create_user_in_db(session, email="test@test.com")

    async def create_inverter():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await login_user(client, "test@test.com", "testpassword123")
            return await client.post("/inverter", json={"name": "Test", "serial": "ABC"})

            # Create 10 concurrent requests
            results = await asyncio.gather(*[create_inverter() for _ in range(10)])

            # Only one should succeed (200), others should get 422
            success_count = sum(1 for r in results if r.status_code == 200)
            failure_count = sum(1 for r in results if r.status_code == 422)

            assert success_count == 1
            assert failure_count == 9

    # clean up
    app.dependency_overrides = {}
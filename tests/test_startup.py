import pytest
from httpx import AsyncClient, ASGITransport

from solar_backend.app import app


@pytest.mark.integration
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_openapi_spec():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/openapi.json')
        assert response.status_code == 200
        assert isinstance(response.json(), dict)


@pytest.mark.integration
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_healthcheck():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/healthcheck')
        assert response.status_code == 200
        assert response.json()["FastAPI"] == "OK"


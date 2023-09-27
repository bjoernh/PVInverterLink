import pytest
from httpx import AsyncClient

from solar_backend.app import app

client = AsyncClient(app=app, base_url='http://test')


@pytest.mark.integration
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_openapi_spec():
    response = await client.get('/openapi.json')
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


@pytest.mark.integration
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_healthcheck():
    response = await client.get('/healthcheck')
    assert response.status_code == 200
    assert response.json()["FastAPI"] == "OK"


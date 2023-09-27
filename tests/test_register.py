import pytest
from httpx import AsyncClient
from solar_backend.db import User
from sqlalchemy import select, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import factory

from faker import Faker

faker = Faker()


@pytest.mark.integration
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_register(client, create_tables):
    response = await client.get("/")
    assert response.status_code == 303
    
    response = await client.get("/signup")
    assert response.status_code == 200

    data = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
        "email": faker.email(),
        "password": faker.password(12),
    }
    response = await client.post("/signup", data=data)
    assert response.status_code == 200
    
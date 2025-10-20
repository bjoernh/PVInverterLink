import pytest
from solar_backend.schemas import UserCreate
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import factory
from faker import Faker
import os

faker = Faker()

class UserFactory(factory.Factory):
    class Meta:
        model = UserCreate

    first_name = faker.first_name()
    last_name = faker.last_name()
    email = faker.email()
    password = faker.password(10)


@pytest.mark.integration
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_register(client, mocker):
    response = await client.get("/")
    assert response.status_code == 303
    
    response = await client.get("/signup")
    assert response.status_code == 200
    
    test_user = UserFactory()

    # mocking send verify email
    mail_mock = mocker.AsyncMock()
    mail_mock.return_value = True
    mocker.patch('solar_backend.users.send_verify_mail', mail_mock)

    response = await client.post("/signup", data=dict(test_user))
    assert response.status_code == 200
    
    assert mail_mock.call_args[1]['email'] == test_user.email
    token = mail_mock.call_args[1]['token']

    response = await client.get(f"/verify?token={token}")
    assert response.status_code == 200

    response = await client.get(f"/login")
    assert response.status_code == 200
    login_data = {
        "username": test_user.email,
        "password": test_user.password,
    }
    response = await client.post("/login", data=login_data)
    assert response.status_code == 200

    
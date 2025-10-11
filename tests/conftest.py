import asyncio
import os
from pathlib import Path
import pytest
from fastapi_htmx import htmx_init
from fastapi.templating import Jinja2Templates
import pytest_asyncio
from solar_backend.db import get_async_session, sessionmanager
from solar_backend.app import app
from httpx import AsyncClient
from solar_backend.api import inverter
from solar_backend import users


DB_TESTING_URI = "sqlite+aiosqlite://"

sessionmanager.init(DB_TESTING_URI)
htmx_init(templates=Jinja2Templates(directory=Path(os.getcwd()) / Path("solar_backend") / Path("templates")))


@pytest.fixture(scope="session")
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def create_tables(event_loop):
    print("Prepare sql tables")
    if sessionmanager._engine is None:
        sessionmanager.init(DB_TESTING_URI)
    async with sessionmanager.connect() as connection:
        await sessionmanager.drop_all(connection)
        await sessionmanager.create_all(connection)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def session_override(event_loop):
    async def get_db_override():
        async with sessionmanager.session() as session:
            yield session
    app.dependency_overrides[get_async_session] = get_db_override


@pytest_asyncio.fixture
async def client(event_loop):
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as c:
        yield c


@pytest.fixture(scope="function")
def without_influx(mocker):
    mocker.patch.object(inverter, 'WEB_DEV_TESTING', True)
    mocker.patch.object(users, 'WEB_DEV_TESTING', True)


@pytest_asyncio.fixture
async def db_session():
    """Provide a database session for tests."""
    async with sessionmanager.session() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user in the database."""
    from tests.helpers import create_user_in_db
    from sqlalchemy.orm import make_transient
    user = await create_user_in_db(
        db_session,
        email="testuser@example.com",
        first_name="Test",
        last_name="User"
    )
    # Force load all attributes before session closes
    _ = (user.id, user.email, user.first_name, user.last_name)
    # Make object transient to avoid session binding issues
    make_transient(user)
    return user


@pytest_asyncio.fixture
async def superuser(db_session):
    """Create a superuser in the database."""
    from tests.helpers import create_user_in_db
    user = await create_user_in_db(
        db_session,
        email="superuser@example.com",
        first_name="Super",
        last_name="User",
        is_superuser=True
    )
    return user


@pytest_asyncio.fixture
async def test_inverter(db_session, test_user):
    """Create a test inverter for the test user."""
    from tests.helpers import create_inverter_in_db
    from sqlalchemy.orm import make_transient
    inverter = await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        name="Test Inverter",
        serial_logger="TEST-123"
    )
    # Force load all attributes before session closes
    _ = (inverter.id, inverter.name, inverter.serial_logger, inverter.influx_bucked_id)
    # Make object transient to avoid session binding issues
    make_transient(inverter)
    return inverter


@pytest_asyncio.fixture
async def authenticated_client(client, test_user):
    """HTTP client with authenticated test user (cookie auth)."""
    from tests.helpers import login_user
    await login_user(client, "testuser@example.com", "testpassword123")
    return client


@pytest_asyncio.fixture
async def bearer_token(client, test_user):
    """Get bearer token for test user."""
    from tests.helpers import get_bearer_token
    token = await get_bearer_token(client, "testuser@example.com", "testpassword123")
    return token


@pytest_asyncio.fixture
async def superuser_token(client, superuser):
    """Get bearer token for superuser."""
    from tests.helpers import get_bearer_token
    token = await get_bearer_token(client, "superuser@example.com", "testpassword123")
    return token
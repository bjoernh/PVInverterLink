import asyncio
import os
from pathlib import Path

# IMPORTANT: Set ENV_FILE before any solar_backend imports
# This ensures settings are loaded from test.env during test execution
if "ENV_FILE" not in os.environ:
    test_env_path = Path(__file__).parent / "test.env"
    # Use relative path from solar_backend/config.py location
    os.environ["ENV_FILE"] = "../tests/test.env"

import pytest
from fastapi_htmx import htmx_init
from fastapi.templating import Jinja2Templates
import pytest_asyncio
from solar_backend.db import get_async_session, sessionmanager
from solar_backend.app import app
from httpx import AsyncClient


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


@pytest_asyncio.fixture
async def async_client(client):
    """Alias for client fixture for consistency with test naming."""
    return client


@pytest_asyncio.fixture
async def async_session(db_session):
    """Alias for db_session fixture for consistency with test naming."""
    return db_session


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
    _ = (inverter.id, inverter.name, inverter.serial_logger)
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


@pytest_asyncio.fixture
async def user_token_headers(bearer_token):
    """Get authorization headers with bearer token for regular user."""
    return {"Authorization": f"Bearer {bearer_token}"}


@pytest_asyncio.fixture
async def superuser_token_headers(superuser_token):
    """Get authorization headers with bearer token for superuser."""
    return {"Authorization": f"Bearer {superuser_token}"}


@pytest.fixture(autouse=True)
def disable_rate_limiter(mocker, request):
    if 'enable_rate_limiter' in request.keywords:
        return
    mocker.patch("solar_backend.limiter.limiter.enabled", False)


@pytest.fixture
def without_influx(mocker):
    """
    Mock InfluxDB/TimescaleDB operations for tests that don't need real time-series data.

    This fixture is kept for backwards compatibility with tests that used it during
    the InfluxDB era. It now returns empty data for time-series queries.
    """
    # Mock time-series query functions to return empty/default data
    mocker.patch(
        'solar_backend.utils.timeseries.get_latest_value',
        side_effect=lambda *args, **kwargs: (None, 0)
    )
    mocker.patch(
        'solar_backend.utils.timeseries.get_power_timeseries',
        return_value=[]
    )
    mocker.patch(
        'solar_backend.utils.timeseries.get_today_energy_production',
        return_value=0.0
    )
    mocker.patch(
        'solar_backend.utils.timeseries.get_today_maximum_power',
        return_value=0
    )
    mocker.patch(
        'solar_backend.utils.timeseries.get_last_hour_average',
        return_value=0
    )
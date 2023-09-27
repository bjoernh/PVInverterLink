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


@pytest.fixture
def client(event_loop):
    c = AsyncClient(app=app, base_url='http://test')
    yield c
import pytest
from fastapi_users.exceptions import InvalidPasswordException
from solar_backend.users import UserManager
from solar_backend.schemas import UserCreate
from solar_backend.db import User
from fastapi_users.db import SQLAlchemyUserDatabase

@pytest.fixture
def user_manager(db_session):
    user_db = SQLAlchemyUserDatabase(db_session, User)
    return UserManager(user_db)

@pytest.fixture
def dummy_user_create():
    return UserCreate(
        email="test@example.com",
        password="password",
        first_name="Test",
        last_name="User",
    )

@pytest.mark.asyncio
async def test_password_too_short(user_manager, dummy_user_create, monkeypatch):
    monkeypatch.setattr("solar_backend.users.WEB_DEV_TESTING", False)
    with pytest.raises(InvalidPasswordException) as excinfo:
        await user_manager.validate_password("short", dummy_user_create)
    assert excinfo.value.reason == "Passwort muss mindestens 8 Zeichen lang sein"

@pytest.mark.asyncio
async def test_password_no_digit(user_manager, dummy_user_create, monkeypatch):
    monkeypatch.setattr("solar_backend.users.WEB_DEV_TESTING", False)
    with pytest.raises(InvalidPasswordException) as excinfo:
        await user_manager.validate_password("longpassword", dummy_user_create)
    assert excinfo.value.reason == "Passwort muss mindestens eine Zahl enthalten"

@pytest.mark.asyncio
async def test_password_no_uppercase(user_manager, dummy_user_create, monkeypatch):
    monkeypatch.setattr("solar_backend.users.WEB_DEV_TESTING", False)
    with pytest.raises(InvalidPasswordException) as excinfo:
        await user_manager.validate_password("longpassword1", dummy_user_create)
    assert excinfo.value.reason == "Passwort muss mindestens einen Großbuchstaben enthalten"

@pytest.mark.asyncio
async def test_common_password(user_manager, dummy_user_create, monkeypatch):
    monkeypatch.setattr("solar_backend.users.WEB_DEV_TESTING", False)
    with pytest.raises(InvalidPasswordException) as excinfo:
        await user_manager.validate_password("password", dummy_user_create)
    assert excinfo.value.reason == "Passwort ist zu einfach"

@pytest.mark.asyncio
async def test_valid_password(user_manager, dummy_user_create, monkeypatch):
    monkeypatch.setattr("solar_backend.users.WEB_DEV_TESTING", False)
    try:
        await user_manager.validate_password("ValidPassword123", dummy_user_create)
    except InvalidPasswordException:
        pytest.fail("Valid password was considered invalid.")

@pytest.mark.asyncio
async def test_validation_disabled_in_dev_mode(user_manager, dummy_user_create, monkeypatch):
    monkeypatch.setattr("solar_backend.users.WEB_DEV_TESTING", True)
    try:
        await user_manager.validate_password("short", dummy_user_create)
    except InvalidPasswordException:
        pytest.fail("Password validation should be disabled in dev mode.")
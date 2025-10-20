import pytest
from unittest.mock import Mock
from fastapi_users.exceptions import InvalidPasswordException
from solar_backend.users import UserManager
from solar_backend.schemas import UserCreate

@pytest.fixture
def user_manager() -> UserManager:
    mock_user_db = Mock()
    return UserManager(mock_user_db)

@pytest.fixture
def mock_user_create() -> UserCreate:
    return UserCreate(
        email="test@example.com",
        password="",
        first_name="Test",
        last_name="User"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_password_too_short(user_manager: UserManager, mock_user_create: UserCreate, mocker):
    mocker.patch("solar_backend.users.WEB_DEV_TESTING", False)
    with pytest.raises(InvalidPasswordException) as excinfo:
        await user_manager.validate_password("short", mock_user_create)
    assert excinfo.value.reason == "Passwort muss mindestens 8 Zeichen lang sein"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_password_no_digit(user_manager: UserManager, mock_user_create: UserCreate, mocker):
    mocker.patch("solar_backend.users.WEB_DEV_TESTING", False)
    with pytest.raises(InvalidPasswordException) as excinfo:
        await user_manager.validate_password("NoDigitPassword", mock_user_create)
    assert excinfo.value.reason == "Passwort muss mindestens eine Zahl enthalten"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_password_no_uppercase(user_manager: UserManager, mock_user_create: UserCreate, mocker):
    mocker.patch("solar_backend.users.WEB_DEV_TESTING", False)
    with pytest.raises(InvalidPasswordException) as excinfo:
        await user_manager.validate_password("nouppercase123", mock_user_create)
    assert excinfo.value.reason == "Passwort muss mindestens einen Großbuchstaben enthalten"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_common_password(user_manager: UserManager, mock_user_create: UserCreate, mocker):
    mocker.patch("solar_backend.users.WEB_DEV_TESTING", False)
    with pytest.raises(InvalidPasswordException) as excinfo:
        await user_manager.validate_password("password", mock_user_create)
    assert excinfo.value.reason == "Passwort ist zu einfach"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_valid_password(user_manager: UserManager, mock_user_create: UserCreate, mocker):
    mocker.patch("solar_backend.users.WEB_DEV_TESTING", False)
    try:
        await user_manager.validate_password("ValidPassword123", mock_user_create)
    except InvalidPasswordException:
        pytest.fail("A valid password should not raise InvalidPasswordException")

@pytest.mark.unit
@pytest.mark.asyncio
async def test_validation_skipped_in_dev_mode(user_manager: UserManager, mock_user_create: UserCreate, mocker):
    mocker.patch("solar_backend.users.WEB_DEV_TESTING", True)
    try:
        await user_manager.validate_password("short", mock_user_create)
    except InvalidPasswordException:
        pytest.fail("Password validation should be skipped in dev testing mode")
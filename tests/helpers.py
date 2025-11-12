"""
Helper functions for common test operations.
"""

from httpx import AsyncClient

from solar_backend.db import Inverter, User
from solar_backend.schemas import UserCreate
from tests.factories import UserCreateFactory


async def create_user_in_db(session, **kwargs) -> User:
    """
    Create a user directly in the database.

    Args:
        session: Database session (can be a fixture that yields or AsyncSession)
        **kwargs: User attributes to override defaults

    Returns:
        Created User object
    """
    from fastapi_users.password import PasswordHelper

    from solar_backend.db import sessionmanager

    password_helper = PasswordHelper()

    defaults = {
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "hashed_password": password_helper.hash("testpassword123"),
        "is_active": True,
        "is_superuser": False,
        "is_verified": True,
    }
    defaults.update(kwargs)

    # Get the actual session - could be a fixture yielding a session or direct session
    async with sessionmanager.session() as db_session:
        user = User(**defaults)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        # Detach from session by accessing ID to ensure it's loaded
        return user


async def create_inverter_in_db(session, user_id: int, **kwargs) -> Inverter:
    """
    Create an inverter directly in the database.

    Args:
        session: Database session (can be a fixture that yields or AsyncSession)
        user_id: ID of the user who owns this inverter
        **kwargs: Inverter attributes to override defaults

    Returns:
        Created Inverter object
    """
    from solar_backend.db import sessionmanager

    defaults = {
        "name": "Test Inverter",
        "serial_logger": "TEST-SERIAL-123",
        "sw_version": "v1.0",
        "user_id": user_id,
        "rated_power": 5000,
        "number_of_mppts": 2,
    }
    defaults.update(kwargs)

    async with sessionmanager.session() as db_session:
        inverter = Inverter(**defaults)
        db_session.add(inverter)
        await db_session.commit()
        await db_session.refresh(inverter)
        # Detach from session by accessing ID to ensure it's loaded
        return inverter


async def login_user(client: AsyncClient, email: str, password: str) -> dict:
    """
    Login a user and return the response with auth cookie.

    Args:
        client: HTTP test client
        email: User email
        password: User password

    Returns:
        Response dict from login endpoint
    """
    response = await client.post("/login", data={"username": email, "password": password})
    return response


async def get_bearer_token(client: AsyncClient, email: str, password: str) -> str:
    """
    Get a bearer token for API authentication.

    Args:
        client: HTTP test client
        email: User email
        password: User password

    Returns:
        JWT bearer token string
    """
    response = await client.post("/auth/jwt/login", data={"username": email, "password": password})
    if response.status_code == 200:
        return response.json()["access_token"]
    raise ValueError(f"Login failed with status {response.status_code}")


async def register_and_verify_user(client: AsyncClient, mocker, user_data: dict = None) -> tuple[UserCreate, str]:
    """
    Register a user and automatically verify their email.

    Args:
        client: HTTP test client
        mocker: pytest-mock fixture
        user_data: Optional user data dict

    Returns:
        Tuple of (UserCreate object, verification token)
    """
    test_user = UserCreateFactory() if user_data is None else UserCreate(**user_data)

    # Mock email sending
    mail_mock = mocker.AsyncMock()
    mail_mock.return_value = True
    mocker.patch("solar_backend.users.send_verify_mail", mail_mock)

    # Register
    response = await client.post("/signup", data=dict(test_user))
    assert response.status_code == 200

    # Get token from mocked email call
    token = mail_mock.call_args[1]["token"]

    # Verify email
    verify_response = await client.get(f"/verify?token={token}")
    assert verify_response.status_code == 200

    return test_user, token

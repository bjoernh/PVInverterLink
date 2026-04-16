"""Single-user self-host mode: auto-create and manage the default user."""

import structlog
from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from solar_backend.config import settings
from solar_backend.db import User, sessionmanager
from solar_backend.utils.api_keys import generate_api_key

logger = structlog.get_logger()


async def ensure_single_user() -> None:
    """Create or update the single-user account on startup.

    Only runs when SINGLE_USER_MODE is enabled. Creates a pre-verified,
    superuser account with an API key for collector authentication.
    """
    if not settings.SINGLE_USER_MODE:
        return

    async with sessionmanager.session() as session:
        user = await session.scalar(select(User).where(User.email == settings.SINGLE_USER_EMAIL))

        if user is None:
            password_helper = PasswordHelper()
            api_key = settings.SINGLE_USER_API_KEY or generate_api_key()
            user = User(
                email=settings.SINGLE_USER_EMAIL,
                hashed_password=password_helper.hash(settings.SINGLE_USER_PASSWORD),
                first_name="Admin",
                last_name="Local",
                is_active=True,
                is_superuser=True,
                is_verified=True,
                api_key=api_key,
            )
            session.add(user)
            await session.commit()
            logger.info(
                "Single-user created",
                email=user.email,
                api_key=api_key,
            )
        else:
            # Ensure user is verified and active, update API key if configured
            user.is_verified = True
            user.is_active = True
            if settings.SINGLE_USER_API_KEY and user.api_key != settings.SINGLE_USER_API_KEY:
                user.api_key = settings.SINGLE_USER_API_KEY
            if not user.api_key:
                user.api_key = generate_api_key()
            await session.commit()
            logger.info(
                "Single-user verified",
                email=user.email,
                api_key=user.api_key,
            )

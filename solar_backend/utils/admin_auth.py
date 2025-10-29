import contextlib
from datetime import datetime, timedelta, timezone
from fastapi import Depends
from sqladmin.authentication import AuthenticationBackend
from fastapi.requests import Request
from fastapi.security import OAuth2PasswordRequestForm
import jwt
import structlog

from solar_backend.config import settings
from solar_backend.db import get_async_session, get_user_db

from solar_backend.users import get_user_manager

get_async_session_context = contextlib.asynccontextmanager(get_async_session)
get_user_db_context = contextlib.asynccontextmanager(get_user_db)
get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)

logger = structlog.get_logger()


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

        async with get_async_session_context() as session:  #TODO: if possible change it to fastapi dependency
            async with get_user_db_context(session) as user_db:
                async with get_user_manager_context(user_db) as user_manager:
                    try:
                        credentials = OAuth2PasswordRequestForm(username=username, password=password)
                        user = await user_manager.authenticate(credentials=credentials)
                    except Exception as e:
                        logger.error("Admin login authentication failed", error=str(e), email=username)
                        return False
                    if not user:
                        logger.warning("Admin login failed: user not authenticated", email=username)
                        return False
                    if not user.is_superuser:
                        logger.warning("Admin login failed: user is not a superuser", user_id=user.id, email=user.email)
                        return False

        try:
            exp = datetime.now(timezone.utc) + timedelta(hours=8)
            token = jwt.encode({
                "email": user.email,
                "user_id": user.id,
                "exp": exp,
                "iat": datetime.now(timezone.utc),
                "is_superuser": True
            }, settings.AUTH_SECRET, algorithm="HS256")

            request.session.update({"token": token})
            logger.info("Admin user logged in", email=user.email, user_id=user.id)
            return True
        except Exception as e:
            logger.error("Error creating token or updating session", error=str(e))
            return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")

        if not token:
            return False

        try:
            payload = jwt.decode(
                token,
                settings.AUTH_SECRET,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )

            if not payload.get("is_superuser"):
                return False

            return True  # Return True for successful authentication
        except jwt.ExpiredSignatureError:
            logger.warning("Admin token expired")
            return False
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid admin token", error=str(e))
            return False


authentication_backend = AdminAuth(secret_key=settings.AUTH_SECRET)
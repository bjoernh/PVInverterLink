import structlog
from typing import Optional
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, IntegerIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqladmin import ModelView
from sqlalchemy import update
from solar_backend.db import User, get_user_db
from solar_backend.config import DEBUG, settings, WEB_DEV_TESTING
from solar_backend.utils.email import send_verify_mail, send_reset_passwort_mail

logger = structlog.get_logger()


from fastapi_users.exceptions import InvalidPasswordException
from solar_backend.schemas import UserCreate


class UserManager(IntegerIDMixin, BaseUserManager[User, int], ModelView):
    reset_password_token_secret = settings.AUTH_SECRET
    verification_token_secret = settings.AUTH_SECRET

    async def validate_password(self, password: str, user: User | UserCreate) -> None:
        if not WEB_DEV_TESTING:
            # Check for common passwords
            common_passwords = ["password", "123456", "12345678", "qwerty"]
            if password.lower() in common_passwords:
                raise InvalidPasswordException(reason="Passwort ist zu einfach")

            if len(password) < 8:
                raise InvalidPasswordException(
                    reason="Passwort muss mindestens 8 Zeichen lang sein"
                )
            if not any(c.isdigit() for c in password):
                raise InvalidPasswordException(
                    reason="Passwort muss mindestens eine Zahl enthalten"
                )
            if not any(c.isupper() for c in password):
                raise InvalidPasswordException(
                    reason="Passwort muss mindestens einen Großbuchstaben enthalten"
                )
        # await super().validate_password(password, user)

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info(f"User {user.email} has registered.", user=user)
        await self.request_verify(user, request=request)

    
    async def on_after_verify(self, user: User, request: Optional[Request] = None):
        logger.info(f"User {user.id} is verified.", user=user)
        # InfluxDB provisioning no longer needed
        # User can immediately start adding inverters
            

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        await send_reset_passwort_mail(user.email, token)
        logger.info(f"User has forgot their password.",user=user, token=token)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        await send_verify_mail(email=user.email, token=token)
        logger.info(f"verify email send to: {user.email}")

 
async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.AUTH_SECRET, lifetime_seconds=60*60*24*2)


auth_backend_user = AuthenticationBackend(
    name="jwt",
    transport=CookieTransport(cookie_secure=settings.COOKIE_SECURE),
    get_strategy=get_jwt_strategy,
)


auth_backend_bearer = AuthenticationBackend(
    name="jwt",
    transport=BearerTransport(tokenUrl="auth/jwt/login"),
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend_user])
fastapi_users_bearer = FastAPIUsers[User, int](get_user_manager,[auth_backend_bearer])

current_active_user = fastapi_users.current_user(active=True, optional=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)

current_active_user_bearer = fastapi_users_bearer.current_user(active=True)
current_superuser_bearer = fastapi_users_bearer.current_user(active=True, superuser=True)

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.last_name]
    name = "User"
    column_searchable_list = [User.email, User.last_name]
    column_sortable_list = [User.id, User.email]
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_details_exclude_list = ["hashed_password"]
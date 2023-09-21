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
from db import User, get_user_db
from solar_backend.config import settings, DEV_TESTING
from solar_backend.utils.influx import inflx
from solar_backend.utils.helpers import send_verify_mail, send_reset_passwort_mail

logger = structlog.get_logger()


class UserManager(IntegerIDMixin, BaseUserManager[User, int], ModelView):
    reset_password_token_secret = settings.AUTH_SECRET
    verification_token_secret = settings.AUTH_SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info(f"User {user.email} has registered.", user=user)
        await self.request_verify(user, request=request)

    
    async def on_after_verify(self, user: User, request: Optional[Request] = None):
        logger.info(f"User {user.id} is verified.", user=user)
        if not DEV_TESTING:
            _inflx_user, org, token = inflx.create_influx_user_and_org(f"{user.email}", user.hashed_password)
            logger.info(f"Influx setup for user {user.first_name} {user.last_name} completed")
            user.influx_org_id = org.id
            user.influx_token = token
            await self.user_db.session.commit()

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
    return JWTStrategy(secret=settings.AUTH_SECRET, lifetime_seconds=3600)


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
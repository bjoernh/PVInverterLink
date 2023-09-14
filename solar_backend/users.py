import structlog

from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, IntegerIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqladmin import ModelView
from db import User, get_user_db, get_async_session
from solar_backend.config import settings
from solar_backend.influx import inflx

logger = structlog.get_logger()


class UserManager(IntegerIDMixin, BaseUserManager[User, int], ModelView):
    reset_password_token_secret = settings.AUTH_SECRET
    verification_token_secret = settings.AUTH_SECRET

    async def on_after_verify(self, user: User, request: Optional[Request] = None):
        logger.info(f"User {user.email} has registered.", user=user)
    
    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info(f"User {user.id} is verified.", user=user)
        #_inflx_user, org = inflx.create_influx_user_and_org(f"{user.email}", user.hashed_password)
        #logger.info(f"Influx setup for user {user.first_name} {user.last_name} completed")
        #user.influx_org_id = org.id
        #await self.user_db.session.commit()

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.last_name]
    name = "User"
    column_searchable_list = [User.email, User.last_name]
    column_sortable_list = [User.id, User.email]
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_details_exclude_list = ["hashed_password"]
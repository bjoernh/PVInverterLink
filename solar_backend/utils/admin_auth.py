from typing import Optional
import contextlib
from fastapi import Depends
from fastapi.responses import RedirectResponse
from fastapi_users import exceptions
from sqladmin import Admin
from sqladmin.authentication import AuthenticationBackend
from fastapi.requests import Request
from fastapi.security import OAuth2PasswordRequestForm
import jwt

from solar_backend.config import settings

from fastapi_users import models
from solar_backend.db import get_async_session, get_user_db

from solar_backend.users import get_user_manager

get_async_session_context = contextlib.asynccontextmanager(get_async_session)
get_user_db_context = contextlib.asynccontextmanager(get_user_db)
get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        async with get_async_session_context() as session:  #TODO: if possible change it to fastapi dependency
            async with get_user_db_context(session) as user_db:
                async with get_user_manager_context(user_db) as user_manager:
                    try:
                        user = await user_manager.authenticate(OAuth2PasswordRequestForm(username=form["username"], password=form["password"]))
                    except:
                        return False
                    if not user:
                        return False
                    if not user.is_superuser:
                        return False
                    
        token  = jwt.encode({"email": user.email}, settings.AUTH_SECRET, algorithm="HS256")
        #ok = user_manager.validate_password(password=password, user=user)

        request.session.update({"token": token})

        return True

    async def logout(self, request: Request) -> bool:
        # Usually you'd want to just clear the session
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Optional[RedirectResponse]:
        token = request.session.get("token")

        if not token:
            return RedirectResponse(request.url_for("admin:login"), status_code=302)

        jwt.decode(token, settings.AUTH_SECRET, algorithms="HS256", verify=True)


authentication_backend = AdminAuth(secret_key=settings.AUTH_SECRET)

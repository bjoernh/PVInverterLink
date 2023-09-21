import structlog
from fastapi_users import BaseUserManager

from typing import Annotated
from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_htmx import htmx
from solar_backend.db import User


from solar_backend.users import get_user_manager, current_active_user

from fastapi_users import models, exceptions
from solar_backend.users import auth_backend_user, get_jwt_strategy

logger = structlog.get_logger()

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
@htmx("login", "login")
async def get_login(request: Request):
    return {}

@router.post("/login")
async def post_login(username: Annotated[str, Form()],
                     password: Annotated[str, Form()],
                     request: Request,
                     user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)):
    
    try:
        user = await user_manager.authenticate(credentials=OAuth2PasswordRequestForm(username=username, password=password))
    except exceptions.UserNotExists:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    
    if user is None or not user.is_active:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)

    response = await auth_backend_user.login(get_jwt_strategy(), user)
    await user_manager.on_after_login(user, request, response)
    
    return RedirectResponse(
        '/',
        headers=response.headers,
        status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout")
async def post_login(request: Request, user: User = Depends(current_active_user)):
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_302_FOUND)
    response = await auth_backend_user.logout(get_jwt_strategy(), user, None)
    return RedirectResponse(
        '/login',
        headers=response.headers,
        status_code=status.HTTP_302_FOUND)
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
async def get_login(request: Request, user: User = Depends(current_active_user)):
    return {"user": user}

@router.post("/login", response_class=HTMLResponse)
async def post_login(username: Annotated[str, Form()],
                     password: Annotated[str, Form()],
                     request: Request,
                     user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)):
    

    user = await user_manager.authenticate(credentials=OAuth2PasswordRequestForm(username=username, password=password))
    
    if user is None or not user.is_active:
        return HTMLResponse("""<div class="alert alert-error">
                                <span><i class="fa-solid fa-circle-xmark"></i> Username oder Passwort falsch</span>
                            </div>""")

    response = await auth_backend_user.login(get_jwt_strategy(), user)
    await user_manager.on_after_login(user, request, response)
    
    response.headers.append("HX-Redirect", "/")
    
    return RedirectResponse(
        '/',
        headers=response.headers,
        status_code=status.HTTP_200_OK)

@router.get("/logout")
async def get_logout(request: Request, user: User = Depends(current_active_user)):
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_302_FOUND)
    response = await auth_backend_user.logout(get_jwt_strategy(), user, None)
    return RedirectResponse(
        '/login',
        headers=response.headers,
        status_code=status.HTTP_302_FOUND)


@router.post("/request_reset_passwort", response_class=HTMLResponse)
async def get_reset_password(request: Request, user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)):
    email = request.headers.get('HX-Prompt')
    user = await user_manager.get_by_email(email)
    await user_manager.forgot_password(user)
    return HTMLResponse("""<div class="alert alert-info">
                                <span><i class="fa-solid fa-circle-info"></i> Email wurde verschickt...</span>
                            </div>""")


@router.get("/reset_passwort")
@htmx("new_password", "new_password")
async def get_reset_password(token: str, request: Request, user: User = Depends(current_active_user), user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)):
    return {"token": token, "user": user}


@router.post("/reset_password", response_class=HTMLResponse)
async def post_reset_password(
    token: Annotated[str, Form()],
    new_password1: Annotated[str, Form()],
    new_password2: Annotated[str, Form()],
    request: Request, 
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)
    ):
    if new_password1 != new_password2:
        return HTMLResponse("""<div class="alert alert-error">
                                <span><i class="fa-solid fa-circle-xmark"></i> Beide neuen Passwörter müssen gleich sein!</span>
                            </div>""")

    try:
        await user_manager.reset_password(token, new_password1)
        return HTMLResponse("""<div class="alert alert-success shadow-lg">
                            <span><i class="fa-solid fa-circle-check"></i> Passwort wurde erfolgreich geändert.</span>
                            <div>
                                <button class="btn btn-sm" hx-get="/login" hx-target="body" hx-push-url="true">Zum Login</button>
                            </div>
                            </div>""")
    except (exceptions.InvalidResetPasswordToken, exceptions.UserInactive, exceptions.UserNotExists) as e:
        logger.error("Password reset failed", error=str(e), token_hash=hash(token))
        return HTMLResponse("""<div class="alert alert-error">
                                <span><i class="fa-solid fa-circle-xmark"></i> Token ist ungültig!</span><button class="btn btn-xs btn-active btn-neutral" hx-get="/login" hx-target="body">Erneut zurücksetzen</Button>
                            </div>""")
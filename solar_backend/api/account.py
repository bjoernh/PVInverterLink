import structlog
from typing import Annotated
from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_htmx import htmx
from fastapi_users import BaseUserManager, models, exceptions
from sqlalchemy import select

from solar_backend.db import User, Inverter, get_async_session
from solar_backend.users import current_active_user, get_user_manager, auth_backend_user, get_jwt_strategy
from solar_backend.limiter import limiter
from solar_backend.config import WEB_DEV_TESTING, settings
from solar_backend.utils.api_keys import generate_api_key

from fastapi_csrf_protect import CsrfProtect

logger = structlog.get_logger()

router = APIRouter()


@router.get("/account", response_class=HTMLResponse)
@htmx("account", "account")
async def get_account(request: Request, user: User = Depends(current_active_user)):
    """Display account management page."""
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    return {"user": user}


@router.post("/account/change-email", response_class=HTMLResponse)
@limiter.limit("5/hour")
async def post_change_email(
    new_email: Annotated[str, Form()],
    request: Request,
    user: User = Depends(current_active_user),
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    csrf_protect: CsrfProtect = Depends()
):
    """Change user email and send verification."""
    if user is None:
        return HTMLResponse(
            """<div class="alert alert-error">
                <span><i class="fa-solid fa-circle-xmark"></i> Sitzung abgelaufen. Bitte melden Sie sich erneut an.</span>
            </div>""",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # Check if new email already exists
    try:
        existing_user = await user_manager.get_by_email(new_email)
        if existing_user and existing_user.id != user.id:
            return HTMLResponse(
                """<div class="alert alert-error">
                    <span><i class="fa-solid fa-circle-xmark"></i> Diese E-Mail-Adresse wird bereits verwendet</span>
                </div>""",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
    except exceptions.UserNotExists:
        pass  # Email is available

    # Update email and require re-verification
    update_dict = {
        "email": new_email,
        "is_verified": False
    }

    await user_manager.user_db.update(user, update_dict)

    # Send verification email
    await user_manager.request_verify(user, request=request)

    logger.info("User email changed", old_email=user.email, new_email=new_email, user_id=user.id)

    return HTMLResponse(
        """<div class="alert alert-success">
            <span><i class="fa-solid fa-circle-check"></i> E-Mail-Adresse geändert! Bitte überprüfen Sie Ihr neues Postfach für die Bestätigungsmail.</span>
        </div>"""
    )


@router.post("/account/change-password", response_class=HTMLResponse)
@limiter.limit("5/hour")
async def post_change_password(
    current_password: Annotated[str, Form()],
    new_password1: Annotated[str, Form()],
    new_password2: Annotated[str, Form()],
    request: Request,
    user: User = Depends(current_active_user),
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    csrf_protect: CsrfProtect = Depends()
):
    """Change user password."""
    if user is None:
        return HTMLResponse(
            """<div class="alert alert-error">
                <span><i class="fa-solid fa-circle-xmark"></i> Sitzung abgelaufen. Bitte melden Sie sich erneut an.</span>
            </div>""",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # Verify current password
    from fastapi.security import OAuth2PasswordRequestForm
    authenticated_user = await user_manager.authenticate(
        credentials=OAuth2PasswordRequestForm(username=user.email, password=current_password)
    )

    if authenticated_user is None:
        return HTMLResponse(
            """<div class="alert alert-error">
                <span><i class="fa-solid fa-circle-xmark"></i> Aktuelles Passwort ist falsch</span>
            </div>""",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # Check new passwords match
    if new_password1 != new_password2:
        return HTMLResponse(
            """<div class="alert alert-error">
                <span><i class="fa-solid fa-circle-xmark"></i> Die neuen Passwörter stimmen nicht überein</span>
            </div>""",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # Validate new password
    try:
        await user_manager.validate_password(new_password1, user)
    except exceptions.InvalidPasswordException as e:
        return HTMLResponse(
            f"""<div class="alert alert-error">
                <span><i class="fa-solid fa-circle-xmark"></i> {e.reason}</span>
            </div>""",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # Update password
    update_dict = {"password": new_password1}
    await user_manager.user_db.update(user, update_dict)

    logger.info("Password updated", user_id=user.id)

    return HTMLResponse(
        """<div class="alert alert-success">
            <span><i class="fa-solid fa-circle-check"></i> Passwort erfolgreich geändert!</span>
        </div>"""
    )


@router.post("/account/delete", response_class=HTMLResponse)
@limiter.limit("3/hour")
async def post_delete_account(
    password: Annotated[str, Form()],
    request: Request,
    user: User = Depends(current_active_user),
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    db_session = Depends(get_async_session),
    csrf_protect: CsrfProtect = Depends()
):
    """Delete user account with full cleanup."""
    if user is None:
        return HTMLResponse(
            """<div class="alert alert-error">
                <span><i class="fa-solid fa-circle-xmark"></i> Sitzung abgelaufen. Bitte melden Sie sich erneut an.</span>
            </div>""",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # Verify password
    from fastapi.security import OAuth2PasswordRequestForm
    authenticated_user = await user_manager.authenticate(
        credentials=OAuth2PasswordRequestForm(username=user.email, password=password)
    )

    if authenticated_user is None:
        return HTMLResponse(
            """<div class="alert alert-error">
                <span><i class="fa-solid fa-circle-xmark"></i> Passwort ist falsch</span>
            </div>""",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # Delete user account and associated data
    async with db_session as session:
        # Get all inverters (will be cascade deleted, but we log them)
        inverters = await session.scalars(select(Inverter).where(Inverter.user_id == user.id))
        inverters = inverters.all()

        logger.info("Deleting user account", user_id=user.id, inverter_count=len(inverters))

        # Delete user (inverters and measurements will be cascade deleted)
        await session.delete(user)
        await session.commit()

    logger.info("User account deleted", user_id=user.id, user_email=user.email)

    # Logout
    response = await auth_backend_user.logout(get_jwt_strategy(), user, None)
    response.headers.append("HX-Redirect", "/login")

    return HTMLResponse(
        """<div class="alert alert-success">
            <span><i class="fa-solid fa-circle-check"></i> Konto erfolgreich gelöscht. Auf Wiedersehen!</span>
        </div>""",
        headers=dict(response.headers)
    )


@router.post("/account/generate-api-key", response_class=HTMLResponse)
@limiter.limit("5/hour")
async def post_generate_api_key(
    request: Request,
    user: User = Depends(current_active_user),
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    csrf_protect: CsrfProtect = Depends()
):
    """Generate a new API key for the user."""
    if user is None:
        return HTMLResponse(
            """<div class="alert alert-error">
                <span><i class="fa-solid fa-circle-xmark"></i> Sitzung abgelaufen. Bitte melden Sie sich erneut an.</span>
            </div>""",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # Generate new API key
    new_api_key = generate_api_key()

    # Update user with new API key
    update_dict = {"api_key": new_api_key}
    await user_manager.user_db.update(user, update_dict)

    logger.info("API key generated", user_id=user.id)

    # Return the new key displayed to the user
    return HTMLResponse(
        f"""<div class="alert alert-success">
            <span><i class="fa-solid fa-circle-check"></i> Neuer API-Schlüssel generiert!</span>
        </div>
        <div class="card bg-base-100 shadow-xl mt-4">
            <div class="card-body">
                <p class="text-sm text-gray-600">Ihr neuer API-Schlüssel:</p>
                <div class="flex items-center gap-2 mt-2">
                    <code class="bg-gray-100 px-3 py-2 rounded font-mono text-sm flex-1">{new_api_key}</code>
                    <button type="button" class="btn btn-sm btn-outline" onclick="navigator.clipboard.writeText('{new_api_key}')">
                        <i class="fa-solid fa-copy"></i>
                    </button>
                </div>
                <p class="text-xs text-gray-500 mt-2">Der alte Schlüssel funktioniert nicht mehr.</p>
            </div>
        </div>"""
    )


@router.get("/account/api-key", response_class=HTMLResponse)
async def get_api_key(
    user: User = Depends(current_active_user),
):
    """Get the current API key for display."""
    if user is None:
        return HTMLResponse(
            """<div class="alert alert-error">
                <span><i class="fa-solid fa-circle-xmark"></i> Sitzung abgelaufen. Bitte melden Sie sich erneut an.</span>
            </div>""",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    if not user.api_key:
        return HTMLResponse(
            """<div class="text-gray-500 text-sm">Kein API-Schlüssel generiert</div>"""
        )

    return HTMLResponse(
        f"""<div class="flex items-center gap-2">
            <code class="bg-gray-100 px-3 py-2 rounded font-mono text-sm flex-1">{user.api_key}</code>
            <button type="button" class="btn btn-sm btn-outline" onclick="navigator.clipboard.writeText('{user.api_key}')">
                <i class="fa-solid fa-copy"></i>
            </button>
        </div>"""
    )

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
from solar_backend.utils.influx import InfluxManagement

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
                <span><i class="fa-solid fa-circle-xmark"></i> Nicht angemeldet</span>
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
    """Change user password in both FastAPI and InfluxDB."""
    if user is None:
        return HTMLResponse(
            """<div class="alert alert-error">
                <span><i class="fa-solid fa-circle-xmark"></i> Nicht angemeldet</span>
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

    # Update FastAPI password
    update_dict = {"password": new_password1}
    await user_manager.user_db.update(user, update_dict)

    # Update InfluxDB password
    if not WEB_DEV_TESTING and user.influx_org_id:
        try:
            async with InfluxManagement(db_url=settings.INFLUX_URL) as inflx:
                inflx.connect(org=settings.INFLUX_OPERATOR_ORG)
                inflx.update_user_password(user.email, new_password1)
                logger.info("Password updated in both FastAPI and InfluxDB", user_id=user.id)
        except Exception as e:
            logger.error(
                "Failed to update InfluxDB password",
                error=str(e),
                user_id=user.id,
                user_email=user.email
            )
            return HTMLResponse(
                """<div class="alert alert-warning">
                    <span><i class="fa-solid fa-triangle-exclamation"></i> Passwort in FastAPI geändert, aber InfluxDB-Aktualisierung fehlgeschlagen. Bitte kontaktieren Sie den Administrator.</span>
                </div>""",
                status_code=status.HTTP_207_MULTI_STATUS
            )
    else:
        logger.info("Password updated in FastAPI only (dev mode or no InfluxDB setup)", user_id=user.id)

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
                <span><i class="fa-solid fa-circle-xmark"></i> Nicht angemeldet</span>
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

    # Get all inverters
    async with db_session as session:
        inverters = await session.scalars(select(Inverter).where(Inverter.user_id == user.id))
        inverters = inverters.all()

        # Delete InfluxDB buckets and organization
        if not WEB_DEV_TESTING and user.influx_org_id:
            try:
                async with InfluxManagement(db_url=settings.INFLUX_URL) as inflx:
                    inflx.connect(org=settings.INFLUX_OPERATOR_ORG)

                    # Delete all inverter buckets
                    for inverter in inverters:
                        if inverter.influx_bucked_id:
                            try:
                                inflx.delete_bucket(inverter.influx_bucked_id)
                                logger.info("Inverter bucket deleted", bucket_id=inverter.influx_bucked_id)
                            except Exception as e:
                                logger.error("Failed to delete inverter bucket", error=str(e), bucket_id=inverter.influx_bucked_id)

                    # Delete user's organization
                    try:
                        inflx.delete_organization(user.influx_org_id)
                        logger.info("User organization deleted", org_id=user.influx_org_id)
                    except Exception as e:
                        logger.error("Failed to delete user organization", error=str(e), org_id=user.influx_org_id)

            except Exception as e:
                logger.error("InfluxDB cleanup failed", error=str(e), user_id=user.id)

        # Delete inverters from database
        for inverter in inverters:
            await session.delete(inverter)

        # Delete user from database
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

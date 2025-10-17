from typing import Annotated

from fastapi_users import BaseUserManager
from pydantic import ValidationError
import structlog

from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_htmx import htmx
from solar_backend.config import settings
from aiosmtplib.errors import SMTPRecipientsRefused
from solar_backend.users import auth_backend_user, get_jwt_strategy
from solar_backend.users import get_user_manager
from pathlib import Path
import os


from solar_backend.schemas import UserCreate
from solar_backend.limiter import limiter

from fastapi_users import models, exceptions

templates = Jinja2Templates(directory=Path(__file__).parent.resolve() / Path("../templates"))


logger = structlog.get_logger()

router = APIRouter()

@router.get("/signup", response_class=HTMLResponse)
@htmx("signup", "signup")
async def root_page(request: Request):
    return {"user": None}


@router.post("/validate-password", response_class=HTMLResponse)
async def validate_password_endpoint(
    password: Annotated[str, Form()],
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)
):
    """
    Validate password in real-time and return error message if invalid.
    Returns empty response if password is valid.
    """
    try:
        # Create a dummy user for validation
        dummy_user = UserCreate(
            first_name="dummy",
            last_name="dummy",
            email="dummy@example.com",
            password=password
        )
        await user_manager.validate_password(password, dummy_user)
        # Password is valid - return empty/success message
        return ""
    except exceptions.InvalidPasswordException as e:
        # Return error message
        return f'<p class="text-red-600 text-sm mt-1" id="password-error">{e.reason}</p>'


from fastapi_csrf_protect import CsrfProtect


from solar_backend.utils.crypto import CryptoManager


@router.post("/signup", response_class=HTMLResponse)
@limiter.limit("3/hour")
async def post_signup(
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    request: Request,
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    csrf_protect: CsrfProtect = Depends()):

    result = True

    try:
        # Encrypt the password for temporary storage
        crypto = CryptoManager(settings.ENCRYPTION_KEY)
        encrypted_password = crypto.encrypt(password)
        user = UserCreate(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,  # For hashing by fastapi-users
            tmp_pass=encrypted_password  # Encrypted for temporary storage
        )
    except ValidationError as e:
        # Return error to password validation div without changing page
        return HTMLResponse(
            f'<p class="text-red-600 text-sm mt-1" id="password-error">Validierungsfehler: {str(e)}</p>',
            headers={"HX-Retarget": "#password-validation", "HX-Reswap": "innerHTML"}
        )

    try:
        await user_manager.create(user)
    except exceptions.InvalidPasswordException as e:
        logger.warning("Password validation failed during signup", error=str(e.reason))
        # Return error to password validation div without changing page
        return HTMLResponse(
            f'<p class="text-red-600 text-sm mt-1" id="password-error">{e.reason}</p>',
            headers={"HX-Retarget": "#password-validation", "HX-Reswap": "innerHTML"}
        )
    except exceptions.UserAlreadyExists:
        # Return error to email field area
        return HTMLResponse(
            f'<p class="text-red-600 text-sm mt-1">Email Adresse ist bereits mit einem Account registriert</p>',
            headers={"HX-Retarget": "#password-validation", "HX-Reswap": "innerHTML"}
        )
    except SMTPRecipientsRefused:
        await user_manager.delete(user)
        # Return error to email field area
        return HTMLResponse(
            f'<p class="text-red-600 text-sm mt-1">Email kann nicht zugestellt werden</p>',
            headers={"HX-Retarget": "#password-validation", "HX-Reswap": "innerHTML"}
        )

    # Success - render verify page
    return templates.TemplateResponse(
        "verify.jinja2",
        {"request": request, "result": result, "email": email}
    )

@router.get("/verify", response_class=HTMLResponse)
async def get_signup(token: str, 
                 request: Request,
                 user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)):
    
    try:
        user = await user_manager.verify(token)
        logger.info(f"{user.email} is now verfied", user=user)
        response = await auth_backend_user.login(get_jwt_strategy(), user)

        return templates.TemplateResponse("complete_verify.jinja2", {"request": request, "result": True}, headers=response.headers)

    except exceptions.UserAlreadyVerified:
        logger.info(f"token was already used to verify", token=token)
        return RedirectResponse(
        '/login',
        status_code=status.HTTP_302_FOUND)

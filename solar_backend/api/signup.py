from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_csrf_protect import CsrfProtect
from fastapi_htmx import htmx
from fastapi_users import BaseUserManager, exceptions, models

from solar_backend.constants import SIGNUP_RATE_LIMIT
from solar_backend.limiter import limiter
from solar_backend.schemas import UserCreate
from solar_backend.users import auth_backend_user, get_jwt_strategy, get_user_manager

templates = Jinja2Templates(directory=Path(__file__).parent.resolve() / Path("../templates"))


logger = structlog.get_logger()

router = APIRouter()


@router.get("/signup", response_class=HTMLResponse)
@htmx("signup", "signup")
async def root_page(request: Request) -> dict:
    return {"user": None}


@router.post("/validate-password", response_class=HTMLResponse)
async def validate_password_endpoint(
    password: Annotated[str, Form()], user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)
) -> HTMLResponse:
    """
    Validate password in real-time and return error message if invalid.
    Returns empty response if password is valid.
    """
    try:
        # Create a dummy user for validation
        dummy_user = UserCreate(first_name="dummy", last_name="dummy", email="dummy@example.com", password=password)
        await user_manager.validate_password(password, dummy_user)
        # Password is valid - return empty/success message
        return HTMLResponse("")
    except exceptions.InvalidPasswordException as e:
        # Return error message
        return HTMLResponse(f'<p class="text-red-600 text-sm mt-1" id="password-error">{e.reason}</p>')


@router.post("/signup", response_class=HTMLResponse)
@limiter.limit(SIGNUP_RATE_LIMIT)
async def post_signup(
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    request: Request,
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    csrf_protect: CsrfProtect = Depends(),
) -> HTMLResponse:
    try:
        user_create = UserCreate(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
        )
        user = await user_manager.create(user_create, safe=True, request=request)
        logger.info(f"User {user.email} created")
        return templates.TemplateResponse("verify.jinja2", {"request": request, "result": True})

    except exceptions.UserAlreadyExists:
        logger.warning(f"User {email} already exists")
        return HTMLResponse("""<div class="alert alert-error">
                                <span><i class="fa-solid fa-circle-xmark"></i> User with this email already exists</span>
                            </div>""")
    except exceptions.InvalidPasswordException as e:
        logger.warning(f"Invalid password for {email}: {e.reason}")
        return HTMLResponse(f"""<div class="alert alert-error">
                                <span><i class="fa-solid fa-circle-xmark"></i> {e.reason}</span>
                            </div>""")
    except Exception as e:
        logger.error(f"Error during signup: {e}")
        return HTMLResponse("""<div class="alert alert-error">
                                <span><i class="fa-solid fa-circle-xmark"></i> An error occurred</span>
                            </div>""")


@router.get("/verify", response_class=HTMLResponse)
async def get_verify(
    token: str, request: Request, user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)
):
    try:
        user = await user_manager.verify(token)
        logger.info(f"{user.email} is now verfied", user=user)
        response = await auth_backend_user.login(get_jwt_strategy(), user)

        return templates.TemplateResponse(
            "complete_verify.jinja2", {"request": request, "result": True}, headers=response.headers
        )

    except exceptions.UserAlreadyVerified:
        logger.info("token was already used to verify", token=token)
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

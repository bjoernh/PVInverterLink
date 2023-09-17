from typing import Annotated

from fastapi_users import BaseUserManager
from pydantic import ValidationError
import structlog

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi_htmx import htmx
from solar_backend.config import settings
from aiosmtplib.errors import SMTPRecipientsRefused

from solar_backend.users import get_user_manager, fastapi_users

from solar_backend.schemas import UserCreate

from fastapi_users import models, exceptions

logger = structlog.get_logger()

router = APIRouter()

@router.get("/signup", response_class=HTMLResponse)
@htmx("signup", "signup")
async def root_page(request: Request):
    return {}


@router.post("/signup", response_class=HTMLResponse)
@htmx("verify", "verify")
async def signup(
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    request: Request,
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)):
    
    result = True
    
    try:
        user = UserCreate(first_name=first_name, last_name=last_name, email=email, password=password)
    except ValidationError as e:
        return {"result": False, "error": str(e)}
    
    try:
        await user_manager.create(user)
    except exceptions.UserAlreadyExists:
        return {"result": False, "error": "Email Adresse ist bereits mit einem Account registriert"}
    except SMTPRecipientsRefused:
        await user_manager.delete(user)
        return {"result": False, "error": "Email kann nicht zugestellt werden"}

            
    return {"result": result ,"email": email}

@router.get("/verify")
@htmx("complete_verify", "complete_verify")
async def signup(token: str, 
                 request: Request,
                 user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)):
    
    try:
        user = await user_manager.verify(token)
        logger.info(f"{user.email} is now verfied", user=user)
    except exceptions.UserAlreadyVerified:
        logger.info(f"{user.email} is already verified", user=user)

    
    return {}
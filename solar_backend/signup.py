from typing import Annotated

from fastapi_users import BaseUserManager
from pydantic import ValidationError
import structlog

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi_htmx import htmx
from solar_backend.config import settings

from solar_backend.users import get_user_manager, fastapi_users

from solar_backend.schemas import UserCreate

from fastapi_users import models

logger = structlog.get_logger()

router = APIRouter()


@router.post("/v1/signup", response_class=HTMLResponse)
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
    await user_manager.create(user)

    return {"result": result ,"email": email}

@router.get("/verify")
@htmx("complete_verify", "complete_verify")
async def signup(token: str, 
                 request: Request,
                 user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager)):
    
    user = await user_manager.verify(token)

    logger.info(f"{user.email} is now verfied", user=user)
    return {}
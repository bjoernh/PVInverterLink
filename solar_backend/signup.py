from typing import Annotated
import contextlib
from pydantic import BaseModel, EmailStr, Field, ValidationError
import structlog
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi_htmx import htmx

from solar_backend.users import get_user_manager
from solar_backend.db import get_async_session, get_user_db
from solar_backend.schemas import UserCreate

logger = structlog.get_logger()

router = APIRouter()

get_async_session_context = contextlib.asynccontextmanager(get_async_session)
get_user_db_context = contextlib.asynccontextmanager(get_user_db)
get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)

async def create_user(first_name: str, last_name: str, email: str, password: str, is_superuser: bool = False):
    async with get_async_session_context() as session:
        async with get_user_db_context(session) as user_db:
            async with get_user_manager_context(user_db) as user_manager:
                user = await user_manager.create(
                    UserCreate(
                        email=email, password=password, is_superuser=is_superuser, last_name=last_name, first_name=first_name
                    )
                )
                logger.info(f"User created {user}")



@router.post("/v1/signup", response_class=HTMLResponse)
@htmx("verify", "verify")
async def signup(
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    request: Request):
    result = True
    try:
        user = UserCreate(first_name=first_name, last_name=last_name, email=email, password=password)
    except ValidationError as e:
        return {"result": False, "error": str(e)}


    #await create_user(*user)
    #TODO: Send verify email
    return {"result": result ,"email": email}
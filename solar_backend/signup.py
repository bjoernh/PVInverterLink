import contextlib
from pydantic import BaseModel, EmailStr, Field
import structlog
from fastapi import APIRouter, Request
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


@router.post("/signup", response_class=HTMLResponse)
@htmx("signup")
async def signup(form: UserCreate, request: Request):
    await create_user(form.first_name, form.last_name, form.email, form.password)
    return {}
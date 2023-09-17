import structlog

from pydantic import ValidationError

from fastapi import APIRouter, Depends, Request, status

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_htmx import htmx
from solar_backend.db import User


from solar_backend.users import current_active_user
from solar_backend.schemas import UserCreate
from fastapi_users import models, exceptions

logger = structlog.get_logger()

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@htmx("start", "start")
async def get_start(request: Request, user: User = Depends(current_active_user)):
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)

    return {"name": user.first_name}
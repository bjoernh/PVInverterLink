import structlog
from pprint import pprint
from pydantic import ValidationError

from fastapi import APIRouter, Depends, Request, status

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_htmx import htmx
from solar_backend.db import Inverter, User, get_async_session

from sqlalchemy import select
from solar_backend.users import current_active_user
from solar_backend.inverter import extend_current_powers
from solar_backend.schemas import UserCreate
from fastapi_users import models, exceptions

logger = structlog.get_logger()

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@htmx("start", "start")
async def get_start(request: Request, user: User = Depends(current_active_user), db_session = Depends(get_async_session)):
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)

    async with db_session as session:
        inverters = await session.scalars(select(Inverter).where(Inverter.user_id == user.id))
        inverters = inverters.all()

    if inverters:
        await extend_current_powers(user, list(inverters))
    
    return {"user": user, "inverters": inverters}

@router.get("/test", response_class=HTMLResponse)
@htmx("test", "test")
async def get_test(request: Request):
    return {"user": None}

@router.post("/post_test")
async def post_test():
    return HTMLResponse("""<a href="/" hx-boost="false">weiter</a>""")
    #extra_headers = {"HX-Redirect": "/", "HX-Refresh":"true"}
    return RedirectResponse('/', status_code=status.HTTP_200_OK, headers=extra_headers)
    #return HTMLResponse("", headers=extra_headers)
    #return HTMLResponse("Seriennummer existiert bereits", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
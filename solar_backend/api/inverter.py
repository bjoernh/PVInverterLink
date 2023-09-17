import structlog
from fastapi_users import BaseUserManager


from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_htmx import htmx

from solar_backend.db import User, get_async_session
from solar_backend.schemas import InverterAdd
from solar_backend.users import current_active_user
from solar_backend.db import Inverter
from solar_backend.inverter import create_influx_bucket


logger = structlog.get_logger()

router = APIRouter()

@router.get("/add_inverter", response_class=HTMLResponse)
@htmx("add_inverter", "add_inverter")
async def get_add_inverter(request: Request):
    return {}

@router.post("/add_inverter")
async def post_add_inverter(inverter_to_add: InverterAdd, db_session = Depends(get_async_session), user: User = Depends(current_active_user)):
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    
    bucket_id = "test-id" #await create_influx_bucket(user, inverter_to_add.name)
    new_inverter_obj = Inverter(user_id=user.id, name=inverter_to_add.name, serial_logger=inverter_to_add.serial, influx_bucked_id=bucket_id, sw_version='-')
    if True:
        async with db_session as session:
            session.add(new_inverter_obj)
            await session.commit()

    
    return RedirectResponse('/', status_code=status.HTTP_303_SEE_OTHER)
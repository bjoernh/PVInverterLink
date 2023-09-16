from fastapi import Depends, FastAPI, Request
from pathlib import Path
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_htmx import htmx, htmx_init
from sqladmin import Admin

from db import User, create_db_and_tables, engine
from schemas import UserCreate, UserRead, UserUpdate
from solar_backend.inverter import InverterAdmin
from solar_backend.users import UserAdmin
from solar_backend import signup
from solar_backend.config import settings
from users import auth_backend, current_active_user, fastapi_users
import structlog

from pydantic import BaseModel, EmailStr, Field

processors = [structlog.dev.ConsoleRenderer()]  # TODO: destinct between dev and production output

structlog.configure(processors)

logger = structlog.get_logger()

app = FastAPI()
htmx_init(templates=Jinja2Templates(directory=Path("templates")))

admin = Admin(app, engine)

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

app.include_router(signup.router)

@app.get("/authenticated-route")
async def authenticated_route(user: User = Depends(current_active_user)):
    return {"message": f"Hello {user.email}!"}


@app.on_event("startup")
async def on_startup():
    # Not needed after setup Alembic
    await create_db_and_tables()

@app.get("/signup", response_class=HTMLResponse)
@htmx("signup", "signup")
async def root_page(request: Request):
    return {}

admin.add_view(UserAdmin)

admin.add_view(InverterAdmin)
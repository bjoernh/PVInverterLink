from fastapi import Depends, FastAPI, Request
from pathlib import Path
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi_htmx import htmx, htmx_init
from sqladmin import Admin

from db import User, create_db_and_tables, engine
from schemas import UserCreate, UserRead, UserUpdate
from solar_backend.inverter import InverterAdmin
from solar_backend.users import UserAdmin
from solar_backend.api import signup, login, start, inverter
from solar_backend.config import settings
from solar_backend.users import auth_backend_bearer, fastapi_users_bearer, current_active_user_bearer
from solar_backend.utils.admin_auth import authentication_backend
import structlog

from pydantic import BaseModel, EmailStr, Field



processors = [structlog.dev.ConsoleRenderer()]  # TODO: destinct between dev and production output

structlog.configure(processors)

logger = structlog.get_logger()

app = FastAPI(title="Deye Hard API",
              redoc_url=None,
              swagger_ui_parameters={
                "persistAuthorization": True,
                "filter": True,
                "displayOperationId": True,
                "displayRequestDuration": True,
                },
)
app.add_middleware(SessionMiddleware, secret_key=settings.AUTH_SECRET)
htmx_init(templates=Jinja2Templates(directory=Path("templates")))

admin = Admin(app=app, authentication_backend=authentication_backend, engine=engine)

# app.include_router(
#     fastapi_users.get_auth_router(auth_backend_user), prefix="/auth/jwt", tags=["auth"]
# )
# app.include_router(
#     fastapi_users.get_register_router(UserRead, UserCreate),
#     prefix="/auth",
#     tags=["auth"],
# )
# app.include_router(
#     fastapi_users.get_reset_password_router(),
#     prefix="/auth",
#     tags=["auth"],
# )
# app.include_router(
#     fastapi_users.get_verify_router(UserRead),
#     prefix="/auth",
#     tags=["auth"],
# )
# app.include_router(
#     fastapi_users.get_users_router(UserRead, UserUpdate),
#     prefix="/users",
#     tags=["users"],
# )

app.include_router(
    fastapi_users_bearer.get_auth_router(auth_backend_bearer),
    prefix="/auth/jwt",
    tags=["auth"],
)


app.include_router(signup.router)
app.include_router(login.router)
app.include_router(start.router)
app.include_router(inverter.router)

admin.add_view(UserAdmin)
admin.add_view(InverterAdmin)

@app.get("/authenticated-route")
async def authenticated_route(user: User = Depends(current_active_user_bearer)):
    return {"message": f"Hello {user.email}!"}
 

@app.on_event("startup")
async def on_startup():
    # Not needed after setup Alembic
    await create_db_and_tables()

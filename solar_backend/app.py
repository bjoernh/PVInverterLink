from fastapi import Depends, FastAPI
from pathlib import Path
import os

from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi_htmx import htmx_init
from sqladmin import Admin
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from solar_backend.db import User, create_db_and_tables, sessionmanager
from solar_backend.inverter import InverterAdmin
from solar_backend.users import UserAdmin
from solar_backend.api import signup, login, start, inverter, healthcheck
from solar_backend.config import settings, WEB_DEV_TESTING
from solar_backend.users import auth_backend_bearer, fastapi_users_bearer, current_active_user_bearer
from solar_backend.utils.admin_auth import authentication_backend
from solar_backend.limiter import limiter
import structlog
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi import Request


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

if not WEB_DEV_TESTING:
    @app.exception_handler(CsrfProtectError)
    def csrf_protect_exception_handler(request: Request, exc: CsrfProtectError):
        return JSONResponse(
            status_code=exc.status_code,
            content={'detail': exc.message}
        )

    class CsrfSettings(BaseModel):
        secret_key: str = settings.AUTH_SECRET
        header_name: str = "HX-CSRF-Token"

    @CsrfProtect.load_config
    def get_csrf_config():
        return CsrfSettings()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SessionMiddleware, secret_key=settings.AUTH_SECRET)
htmx_init(templates=Jinja2Templates(directory=Path(os.getcwd()) / Path("templates")))

sessionmanager.init(settings.DATABASE_URL)
admin = Admin(app=app, authentication_backend=authentication_backend, engine=sessionmanager.engine)

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
app.include_router(healthcheck.router)

admin.add_view(UserAdmin)
admin.add_view(InverterAdmin)

@app.get("/authenticated-route")
async def authenticated_route(user: User = Depends(current_active_user_bearer)):
    return {"message": f"Hello {user.email}!"}
 

@app.on_event("startup")
async def on_startup():
    # Not needed after setup Alembic
    await create_db_and_tables()
from fastapi import Depends, FastAPI, HTTPException, status
from pathlib import Path
import os

from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi_htmx import htmx_init
from sqladmin import Admin
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from solar_backend.db import User, create_db_and_tables, sessionmanager, InverterAdmin, DCChannelMeasurementAdmin
from solar_backend.users import UserAdmin
from solar_backend.api import signup, login, start, inverter, healthcheck, account, dashboard, measurements, export, dc_channels
from solar_backend.config import settings
from solar_backend.users import auth_backend_bearer, fastapi_users_bearer, current_active_user_bearer
from solar_backend.utils.admin_auth import authentication_backend
from solar_backend.config import settings
from solar_backend.limiter import limiter
from solar_backend.constants import UNAUTHORIZED_MESSAGE
from solar_backend.utils.logging import configure_logging
import structlog
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from pydantic import BaseModel
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi import Request

configure_logging()

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

# Mount static files for CSS and other assets
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    logger.warning(f"Static directory not found at {static_dir}")

@app.exception_handler(CsrfProtectError)
def csrf_protect_exception_handler(request: Request, exc: CsrfProtectError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={'detail': exc.message}
    )

class CsrfSettings(BaseModel):
    secret_key: str = settings.AUTH_SECRET
    header_name: str = "HX-CSRF-Token"

@CsrfProtect.load_config
def get_csrf_config() -> CsrfSettings:
    return CsrfSettings()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Handle 401 Unauthorized (expired sessions, missing auth)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse | RedirectResponse:
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # For HTML/HTMX requests, redirect to login page
        if "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        # For API requests, return JSON error with helpful message
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "unauthorized",
                "message": UNAUTHORIZED_MESSAGE + " Please log in again.",
                "details": {}
            }
        )
    # For other HTTP exceptions, use default behavior
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

app.add_middleware(SessionMiddleware, secret_key=settings.AUTH_SECRET)
htmx_init(templates=Jinja2Templates(directory=Path(os.getcwd()) / Path("templates")))

sessionmanager.init(settings.DATABASE_URL)
admin = Admin(app=app, authentication_backend=authentication_backend, engine=sessionmanager.engine)

app.include_router(
    fastapi_users_bearer.get_auth_router(auth_backend_bearer),
    prefix="/auth/jwt",
    tags=["auth"],
)


app.include_router(signup.router)
app.include_router(login.router)
app.include_router(start.router)
app.include_router(inverter.router)
app.include_router(account.router)
app.include_router(dashboard.router)
app.include_router(dc_channels.router)
app.include_router(export.router)
app.include_router(measurements.router, tags=["measurements", "opendtu"])
app.include_router(healthcheck.router)

admin.add_view(UserAdmin)
admin.add_view(InverterAdmin)
admin.add_view(DCChannelMeasurementAdmin)

@app.get("/authenticated-route")
async def authenticated_route(user: User = Depends(current_active_user_bearer)) -> dict[str, str]:
    return {"message": f"Hello {user.email}!"}
 

@app.on_event("startup")
async def on_startup() -> None:
    # Not needed after setup Alembic
    await create_db_and_tables()
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, BaseModel
from fastapi_mail import ConnectionConfig, FastMail
from pathlib import Path
import os
import structlog

logger = structlog.get_logger()

ENF_FILE = os.environ.get("ENV_FILE", None)
if ENF_FILE is None:
    logger.critical("No Env File found, check if ENV_FILE is defined")
    path_to_env = None
else:
    path_to_env = Path(__file__).parent.resolve() / Path(ENF_FILE)


class MailSettings(BaseModel):
    SUPPRESS_SEND: bool
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=path_to_env,
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )
    DATABASE_URL: str = "postgresql+asyncpg://deyehard:dev-testing-ok@localhost:5432/deyehard"  # Default for local dev
    AUTH_SECRET: str = (
        "development-secret-key-change-in-production"  # Default for local dev
    )
    ENCRYPTION_KEY: str = "6DLfBB4KnMuChUJZsMHWz2kJTtNRNTTtoTCCbH7CYyw="
    BASE_URL: AnyHttpUrl = "http://localhost:8001"  # Default for local dev
    FASTMAIL: ConnectionConfig | None = None  # Optional for local dev
    COOKIE_SECURE: bool = False  # False for local dev, True in production
    TZ: str = "Europe/Berlin"  # Default timezone for time display (Docker convention)
    STORE_DC_CHANNEL_DATA: bool = True  # Store detailed DC channel (MPPT) measurements from inverters


settings = Settings()

fastmail = FastMail(settings.FASTMAIL) if settings.FASTMAIL else None

WEB_DEV_TESTING = False  # Legacy flag - can be removed in future cleanup

DEBUG = False  # turn on echo mode of sqlalchemy

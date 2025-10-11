from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, BaseModel, AnyUrl
from fastapi_mail import ConnectionConfig, FastMail, ConnectionConfig
from pathlib import Path
import os
import structlog
logger = structlog.get_logger()

ENF_FILE = os.environ.get('ENV_FILE', None)
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
    model_config = SettingsConfigDict(env_file=path_to_env, env_file_encoding='utf-8', extra='ignore', env_nested_delimiter='__')
    DATABASE_URL: str
    AUTH_SECRET: str
    ENCRYPTION_KEY: str = "6DLfBB4KnMuChUJZsMHWz2kJTtNRNTTtoTCCbH7CYyw="
    INFLUX_URL: str
    INFLUX_OPERATOR_TOKEN: str
    INFLUX_OPERATOR_ORG: str = "wtf"
    BASE_URL: AnyHttpUrl
    FASTMAIL: ConnectionConfig
    COOKIE_SECURE: bool = True

settings = Settings()

fastmail = FastMail(settings.FASTMAIL)

WEB_DEV_TESTING = False  # setting to true will disable influx user, org and bucket creation for developing

DEBUG = False  # turn on echo mode of sqlalchemy
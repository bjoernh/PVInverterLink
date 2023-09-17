from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, BaseModel, AnyUrl
from fastapi_mail import ConnectionConfig, FastMail, ConnectionConfig
from ipaddress import IPv4Address

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
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore', env_nested_delimiter='__')
    DATABASE_URL: str
    AUTH_SECRET: str
    INFLUX_URL: AnyHttpUrl
    BASE_URL: AnyHttpUrl
    FASTMAIL: ConnectionConfig

settings = Settings(_env_file='.env', _env_file_encoding='utf-8')

fastmail = FastMail(settings.FASTMAIL)
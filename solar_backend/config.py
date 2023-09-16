from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, BaseModel
from fastapi_mail import ConnectionConfig

class MailSettings(BaseModel):
    MAIL_SUPPRESS_SEND: bool
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
    INFLUX_URL: str
    FASTMAIL: MailSettings

settings = Settings(_env_file='.env', _env_file_encoding='utf-8')

mail_conf = ConnectionConfig(*settings.FASTMAIL.model_dump())
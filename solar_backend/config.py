from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    DATABASE_URL: str
    AUTH_SECRET: str

settings = Settings(_env_file='.env', _env_file_encoding='utf-8')

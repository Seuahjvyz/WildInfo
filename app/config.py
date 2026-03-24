from pydantic_settings import BaseSettings
from pydantic import PostgresDsn

class Settings(BaseSettings):
    DATABASE_URL: PostgresDsn
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_PRE_PING: bool = True
    KEEP_ALIVE_INTERVAL_SECONDS: int = 180
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
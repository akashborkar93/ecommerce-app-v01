from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """All environment-specific configuration. Host and credentials have no defaults."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_host: str
    database_port: int = 5432
    database_name: str
    database_user: str
    database_password: str

    app_env: str = "development"
    log_level: str = "INFO"
    service_name: str = "ecommerce-api"
    database_connect_timeout: int = 5

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

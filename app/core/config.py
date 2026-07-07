from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor centinela definido en .env.example. Cuando DATABASE_URL conserva este
# valor (o esta vacio) usamos una BD SQLite local para poder desarrollar sin
# depender del proveedor cloud. El contrato de la app no cambia.
BDD_CLOUD_SENTINEL = "BDD_CLOUD"
LOCAL_DEV_DATABASE_URL = "sqlite:///./pronostats_dev.db"



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "PronoStats API"
    api_version: str = "0.1.0"

    # Base de datos en la nube (abstraida via DATABASE_URL).
    database_url: str = BDD_CLOUD_SENTINEL

    # Seguridad / JWT
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    jwt_cookie_name: str = "access_token"
    jwt_cookie_secure: bool = False
    jwt_cookie_samesite: str = "lax"

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Motor de pronostico
    prediction_model_version: str = "rules-v1"
    prediction_recent_form_matches: int = 5
    prediction_home_advantage: float = 0.15

    @property
    def effective_database_url(self) -> str:
        if not self.database_url or self.database_url == BDD_CLOUD_SENTINEL:
            return LOCAL_DEV_DATABASE_URL
        return self.database_url

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

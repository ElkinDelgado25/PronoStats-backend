from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor centinela definido en .env.example. Cuando DATABASE_URL conserva este
# valor (o esta vacio) usamos una BD SQLite local para poder desarrollar sin
# depender del proveedor cloud. El contrato de la app no cambia.
BDD_CLOUD_SENTINEL = "BDD_CLOUD"
LOCAL_DEV_DATABASE_URL = "sqlite:///./pronostats_dev.db"

JWT_SECRET_PLACEHOLDERS = {
    "",
    "dev-secret-change-me",
    "cambia-esto-por-un-secreto-largo-y-aleatorio",
    "REEMPLAZA_CON_UN_SECRETO_DE_32_CARACTERES_MINIMO",
}
ALLOWED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}
ALLOWED_COOKIE_SAMESITE = {"lax", "strict", "none"}
PRODUCTION_ENVIRONMENTS = {"production", "prod"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "PronoStats API"
    api_version: str = "0.1.0"
    environment: str = "development"

    # Base de datos en la nube (abstraida via DATABASE_URL).
    database_url: str = BDD_CLOUD_SENTINEL

    # Seguridad / JWT
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    jwt_cookie_name: str = "access_token"
    jwt_cookie_secure: bool | None = None
    jwt_cookie_samesite: str = "lax"

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Stripe (cartera)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_currency: str = "usd"
    stripe_min_deposit: float = 5.0
    frontend_url: str = "http://localhost:5173"
    stripe_allow_confirm_fallback: bool = True

    # Motor de pronostico
    prediction_model_version: str = "rules-v1"
    prediction_recent_form_matches: int = 5
    prediction_home_advantage: float = 0.15
    prediction_overround_margin: float = 0.07

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        self.environment = self.environment.lower().strip()
        self.jwt_algorithm = self.jwt_algorithm.upper().strip()
        self.jwt_cookie_samesite = self.jwt_cookie_samesite.lower().strip()

        if self.jwt_secret.strip() in JWT_SECRET_PLACEHOLDERS:
            raise ValueError(
                "JWT_SECRET debe definirse con un valor aleatorio y no reutilizable"
            )
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET debe tener al menos 32 caracteres")
        if self.jwt_algorithm not in ALLOWED_JWT_ALGORITHMS:
            raise ValueError("JWT_ALGORITHM debe ser HS256, HS384 o HS512")
        if self.jwt_cookie_samesite not in ALLOWED_COOKIE_SAMESITE:
            raise ValueError("JWT_COOKIE_SAMESITE debe ser lax, strict o none")
        if "*" in self.cors_origins_list:
            raise ValueError("CORS_ORIGINS no puede usar '*' con cookies de sesion")
        # JWT_COOKIE_SECURE=false se permite tambien en production para HTTP.
        # En Cloud Run / Render (HTTPS) usa JWT_COOKIE_SECURE=true.
        if self.jwt_cookie_samesite == "none" and not self.effective_jwt_cookie_secure:
            raise ValueError("JWT_COOKIE_SAMESITE=none requiere JWT_COOKIE_SECURE=true")
        if not (0.05 <= self.prediction_overround_margin <= 0.08):
            raise ValueError("PREDICTION_OVERROUND_MARGIN debe estar entre 0.05 y 0.08")
        return self


    @property
    def is_production(self) -> bool:
        return self.environment in PRODUCTION_ENVIRONMENTS

    @property
    def effective_jwt_cookie_secure(self) -> bool:
        if self.jwt_cookie_secure is None:
            return self.is_production
        return self.jwt_cookie_secure

    @property
    def effective_database_url(self) -> str:
        if not self.database_url or self.database_url == BDD_CLOUD_SENTINEL:
            return LOCAL_DEV_DATABASE_URL
        return self.database_url

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key.startswith("sk_"))

    @property
    def stripe_confirm_fallback_enabled(self) -> bool:
        return not self.is_production and self.stripe_allow_confirm_fallback


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

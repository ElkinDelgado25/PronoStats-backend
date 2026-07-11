from contextlib import asynccontextmanager
import re
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    admin,
    analysis_history,
    auth,
    boletos,
    combinadas,
    favorites,
    leagues,
    matches,
    predictions,
    stats,
    stripe_wallet,
    teams,
)
from app.core.config import settings
from app.csv_store import store
from app.db.base import Base
from app.db.session import engine

# Importa los modelos para que queden registrados en Base.metadata.
import app.models  # noqa: F401

CSRF_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DEV_ORIGIN_PATTERN = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def _origin_from_request(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")

    referer = request.headers.get("referer")
    if not referer:
        return None
    parsed = urlsplit(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_allowed_origin(origin: str) -> bool:
    if origin in settings.cors_origins_list:
        return True
    if not settings.is_production:
        return bool(re.fullmatch(DEV_ORIGIN_PATTERN, origin))
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tablas de la BD (usuarios/auth). En produccion usar Alembic.
    Base.metadata.create_all(bind=engine)
    # Relee los datasets CSV (data/dataset_futbol/) en CADA arranque y
    # recalcula pronosticos y metricas. Los datos de negocio NO se persisten
    # en la BD: viven en memoria y provienen exclusivamente de los CSV.
    store.load()
    print(
        f"[csv_store] CSV leidos: {len(store.ligas)} ligas, "
        f"{len(store.equipos)} equipos y {len(store.partidos)} partidos.",
        flush=True,
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    description="API de pronosticos deportivos basados en estadisticas historicas.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list if settings.is_production else [],
    allow_origin_regex=None if settings.is_production else DEV_ORIGIN_PATTERN,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def csrf_origin_guard(request: Request, call_next):
    if (
        request.method.upper() in CSRF_PROTECTED_METHODS
        and request.cookies.get(settings.jwt_cookie_name)
    ):
        origin = _origin_from_request(request)
        if origin and not _is_allowed_origin(origin):
            return JSONResponse(
                status_code=403,
                content={"detail": "Origen no permitido para esta sesion"},
            )
    return await call_next(request)

app.include_router(auth.router)
app.include_router(leagues.router)
app.include_router(teams.router)
app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(combinadas.router)
app.include_router(boletos.router)
app.include_router(stripe_wallet.router)
app.include_router(favorites.router)
app.include_router(analysis_history.router)
app.include_router(stats.router)
app.include_router(admin.router)


@app.get("/", tags=["health"])
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.api_version}

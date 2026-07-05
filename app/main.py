from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    auth,
    favorites,
    leagues,
    matches,
    predictions,
    stats,
    teams,
)
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

# Importa los modelos para que queden registrados en Base.metadata.
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # En dev (SQLite) crea las tablas automaticamente. En produccion usar Alembic.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    description="API de pronosticos deportivos basados en estadisticas historicas.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(leagues.router)
app.include_router(teams.router)
app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(favorites.router)
app.include_router(stats.router)
app.include_router(admin.router)


@app.get("/", tags=["health"])
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.api_version}

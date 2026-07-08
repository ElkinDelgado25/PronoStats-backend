from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    auth,
    combinadas,
    favorites,
    leagues,
    matches,
    predictions,
    stats,
    teams,
)
from app.core.config import settings
from app.csv_store import store
from app.db.base import Base
from app.db.session import engine

# Importa los modelos para que queden registrados en Base.metadata.
import app.models  # noqa: F401


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
app.include_router(combinadas.router)
app.include_router(favorites.router)
app.include_router(stats.router)
app.include_router(admin.router)


@app.get("/", tags=["health"])
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.api_version}

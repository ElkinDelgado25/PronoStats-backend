from fastapi import APIRouter, HTTPException, Query

from app.csv_store import store
from app.schemas.equipo import EquipoOut, EquipoStats

router = APIRouter(prefix="/teams", tags=["equipos"])


@router.get("", response_model=list[EquipoOut])
def listar_equipos(league_id: int | None = Query(default=None)) -> list:
    """Equipos provenientes del dataset CSV (equipos.csv)."""
    return store.get_equipos(league_id)


@router.get("/{equipo_id}/stats", response_model=EquipoStats)
def stats_equipo(equipo_id: int) -> dict:
    """HU-12: estadisticas historicas del equipo calculadas sobre goles.csv."""
    stats = store.get_team_stats(equipo_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return stats

from fastapi import APIRouter, HTTPException, Query

from app.csv_store import store
from app.schemas.equipo import EquipoComparacionOut, EquipoOut, EquipoStats

router = APIRouter(prefix="/teams", tags=["equipos"])


@router.get("", response_model=list[EquipoOut])
def listar_equipos(league_id: int | None = Query(default=None)) -> list:
    """Equipos provenientes del dataset CSV (equipos.csv)."""
    return store.get_equipos(league_id)


@router.get("/compare", response_model=EquipoComparacionOut)
def comparar_equipos(
    equipo_a_id: int = Query(gt=0),
    equipo_b_id: int = Query(gt=0),
) -> dict:
    """HU-11: comparacion de dos equipos usando estadisticas historicas."""
    comparacion = store.compare_teams(equipo_a_id, equipo_b_id)
    if comparacion is None:
        raise HTTPException(
            status_code=400,
            detail="Selecciona dos equipos existentes y diferentes",
        )
    return comparacion


@router.get("/{equipo_id}/stats", response_model=EquipoStats)
def stats_equipo(equipo_id: int) -> dict:
    """HU-12: estadisticas historicas del equipo calculadas sobre goles.csv."""
    stats = store.get_team_stats(equipo_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return stats

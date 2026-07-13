from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.csv_store import store
from app.schemas.partido import EnfrentamientoH2H, PartidoOut

router = APIRouter(prefix="/matches", tags=["partidos"])


@router.get("", response_model=list[PartidoOut])
def listar_partidos(
    league_id: int | None = Query(default=None),
    fecha: date | None = Query(default=None),
    estado: str | None = Query(default=None),
) -> list:
    """HU-04 y HU-05: catalogo de partidos (desde goles.csv) con filtros."""
    return store.get_partidos(liga_id=league_id, fecha=fecha, estado=estado)


@router.get("/{partido_id}", response_model=PartidoOut)
def detalle_partido(partido_id: int):
    partido = store.get_partido(partido_id)
    if partido is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido


@router.get("/{partido_id}/h2h", response_model=EnfrentamientoH2H)
def head_to_head(partido_id: int) -> dict:
    """HU-06: historial de enfrentamientos entre los dos equipos del partido."""
    h2h = store.get_h2h(partido_id)
    if h2h is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return h2h

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.equipo import Equipo
from app.schemas.equipo import EquipoOut, EquipoStats
from app.services.team_stats import compute_team_form

router = APIRouter(prefix="/teams", tags=["equipos"])


@router.get("", response_model=list[EquipoOut])
def listar_equipos(
    league_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Equipo]:
    stmt = select(Equipo).order_by(Equipo.nombre)
    if league_id is not None:
        stmt = stmt.where(Equipo.liga_id == league_id)
    return list(db.execute(stmt).scalars().all())


@router.get("/{equipo_id}/stats", response_model=EquipoStats)
def stats_equipo(equipo_id: int, db: Session = Depends(get_db)) -> EquipoStats:
    """HU-12: Estadisticas historicas de un equipo."""
    equipo = db.get(Equipo, equipo_id)
    if equipo is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    # limite grande para considerar todo el historial disponible
    forma = compute_team_form(db, equipo_id, limit=1000)
    return EquipoStats(
        equipo_id=equipo.id,
        nombre=equipo.nombre,
        partidos_jugados=forma.partidos_jugados,
        victorias=forma.victorias,
        empates=forma.empates,
        derrotas=forma.derrotas,
        goles_favor=forma.goles_favor,
        goles_contra=forma.goles_contra,
        promedio_goles_favor=round(forma.promedio_goles_favor, 2),
        promedio_goles_contra=round(forma.promedio_goles_contra, 2),
    )

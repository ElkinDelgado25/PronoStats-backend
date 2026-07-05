from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.partido import EstadoPartido, Partido
from app.schemas.partido import EnfrentamientoH2H, PartidoOut

router = APIRouter(prefix="/matches", tags=["partidos"])


@router.get("", response_model=list[PartidoOut])
def listar_partidos(
    league_id: int | None = Query(default=None),
    fecha: date | None = Query(default=None),
    estado: EstadoPartido | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Partido]:
    """HU-04 y HU-05: catalogo de partidos con filtros por liga, fecha y estado."""
    stmt = select(Partido).order_by(Partido.fecha.asc())
    if league_id is not None:
        stmt = stmt.where(Partido.liga_id == league_id)
    if estado is not None:
        stmt = stmt.where(Partido.estado == estado)
    if fecha is not None:
        inicio = datetime.combine(fecha, time.min)
        fin = datetime.combine(fecha, time.max)
        stmt = stmt.where(and_(Partido.fecha >= inicio, Partido.fecha <= fin))
    return list(db.execute(stmt).scalars().all())


@router.get("/{partido_id}", response_model=PartidoOut)
def detalle_partido(partido_id: int, db: Session = Depends(get_db)) -> Partido:
    partido = db.get(Partido, partido_id)
    if partido is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido


@router.get("/{partido_id}/h2h", response_model=EnfrentamientoH2H)
def head_to_head(partido_id: int, db: Session = Depends(get_db)) -> EnfrentamientoH2H:
    """HU-06: historial de enfrentamientos entre los dos equipos del partido."""
    partido = db.get(Partido, partido_id)
    if partido is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    a, b = partido.local_id, partido.visitante_id
    stmt = (
        select(Partido)
        .where(
            Partido.estado == EstadoPartido.finalizado,
            or_(
                and_(Partido.local_id == a, Partido.visitante_id == b),
                and_(Partido.local_id == b, Partido.visitante_id == a),
            ),
        )
        .order_by(Partido.fecha.desc())
    )
    historial = list(db.execute(stmt).scalars().all())

    victorias_local = empates = victorias_visitante = 0
    for p in historial:
        if p.resultado is None:
            continue
        ganador = p.resultado.ganador
        if ganador == "empate":
            empates += 1
        elif (ganador == "local" and p.local_id == a) or (
            ganador == "visitante" and p.visitante_id == a
        ):
            victorias_local += 1
        else:
            victorias_visitante += 1

    return EnfrentamientoH2H(
        total_partidos=len(historial),
        victorias_local=victorias_local,
        empates=empates,
        victorias_visitante=victorias_visitante,
        historial=historial,
    )

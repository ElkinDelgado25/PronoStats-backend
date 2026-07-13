from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.equipo import Equipo
from app.models.liga import Liga
from app.models.partido import EstadoPartido, Partido
from app.models.prediccion import Prediccion
from app.models.resultado import Resultado
from app.models.usuario import Usuario
from app.schemas.equipo import EquipoCreate, EquipoOut, EquipoUpdate
from app.schemas.liga import LigaCreate, LigaOut, LigaUpdate
from app.schemas.partido import (
    PartidoCreate,
    PartidoOut,
    PartidoUpdate,
    ResultadoIn,
)
from app.schemas.stats import UsageStats
from app.services.evaluation import evaluar_prediccion

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


# ------------------------- Ligas (HU-15) -------------------------
@router.post("/leagues", response_model=LigaOut, status_code=status.HTTP_201_CREATED)
def crear_liga(payload: LigaCreate, db: Session = Depends(get_db)) -> Liga:
    liga = Liga(**payload.model_dump())
    db.add(liga)
    db.commit()
    db.refresh(liga)
    return liga


@router.put("/leagues/{liga_id}", response_model=LigaOut)
def actualizar_liga(
    liga_id: int, payload: LigaUpdate, db: Session = Depends(get_db)
) -> Liga:
    liga = db.get(Liga, liga_id)
    if liga is None:
        raise HTTPException(status_code=404, detail="Liga no encontrada")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(liga, campo, valor)
    db.commit()
    db.refresh(liga)
    return liga


@router.delete("/leagues/{liga_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_liga(liga_id: int, db: Session = Depends(get_db)) -> None:
    liga = db.get(Liga, liga_id)
    if liga is None:
        raise HTTPException(status_code=404, detail="Liga no encontrada")
    db.delete(liga)
    db.commit()


# ------------------------- Equipos (HU-16) -------------------------
@router.post("/teams", response_model=EquipoOut, status_code=status.HTTP_201_CREATED)
def crear_equipo(payload: EquipoCreate, db: Session = Depends(get_db)) -> Equipo:
    if db.get(Liga, payload.liga_id) is None:
        raise HTTPException(status_code=404, detail="Liga no encontrada")
    equipo = Equipo(**payload.model_dump())
    db.add(equipo)
    db.commit()
    db.refresh(equipo)
    return equipo


@router.put("/teams/{equipo_id}", response_model=EquipoOut)
def actualizar_equipo(
    equipo_id: int, payload: EquipoUpdate, db: Session = Depends(get_db)
) -> Equipo:
    equipo = db.get(Equipo, equipo_id)
    if equipo is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(equipo, campo, valor)
    db.commit()
    db.refresh(equipo)
    return equipo


@router.delete("/teams/{equipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_equipo(equipo_id: int, db: Session = Depends(get_db)) -> None:
    equipo = db.get(Equipo, equipo_id)
    if equipo is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    db.delete(equipo)
    db.commit()


# ------------------------- Partidos (HU-16) -------------------------
def _validar_partido(db: Session, liga_id: int, local_id: int, visitante_id: int) -> None:
    if local_id == visitante_id:
        raise HTTPException(status_code=400, detail="Un equipo no puede jugar contra si mismo")
    if db.get(Liga, liga_id) is None:
        raise HTTPException(status_code=404, detail="Liga no encontrada")
    for eid in (local_id, visitante_id):
        if db.get(Equipo, eid) is None:
            raise HTTPException(status_code=404, detail=f"Equipo {eid} no encontrado")


@router.post("/matches", response_model=PartidoOut, status_code=status.HTTP_201_CREATED)
def crear_partido(payload: PartidoCreate, db: Session = Depends(get_db)) -> Partido:
    _validar_partido(db, payload.liga_id, payload.local_id, payload.visitante_id)
    partido = Partido(**payload.model_dump())
    db.add(partido)
    db.commit()
    db.refresh(partido)
    return partido


@router.put("/matches/{partido_id}", response_model=PartidoOut)
def actualizar_partido(
    partido_id: int, payload: PartidoUpdate, db: Session = Depends(get_db)
) -> Partido:
    partido = db.get(Partido, partido_id)
    if partido is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(partido, campo, valor)
    db.commit()
    db.refresh(partido)
    return partido


@router.delete("/matches/{partido_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_partido(partido_id: int, db: Session = Depends(get_db)) -> None:
    partido = db.get(Partido, partido_id)
    if partido is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    db.delete(partido)
    db.commit()


@router.put("/matches/{partido_id}/result", response_model=PartidoOut)
def cargar_resultado(
    partido_id: int, payload: ResultadoIn, db: Session = Depends(get_db)
) -> Partido:
    """Carga el resultado real, marca el partido como finalizado y evalua la prediccion."""
    partido = db.get(Partido, partido_id)
    if partido is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    if partido.resultado is None:
        partido.resultado = Resultado(
            partido_id=partido.id,
            goles_local=payload.goles_local,
            goles_visitante=payload.goles_visitante,
        )
    else:
        partido.resultado.goles_local = payload.goles_local
        partido.resultado.goles_visitante = payload.goles_visitante

    partido.estado = EstadoPartido.finalizado
    db.flush()
    # Evalua la prediccion existente contra el resultado real (aciertos vs fallos).
    evaluar_prediccion(partido)
    db.commit()
    db.refresh(partido)
    return partido


# ------------------------- Reportes (HU-17) -------------------------
@router.get("/usage-stats", response_model=UsageStats)
def usage_stats(db: Session = Depends(get_db)) -> UsageStats:
    def _count(model) -> int:
        return db.execute(select(func.count()).select_from(model)).scalar_one()

    return UsageStats(
        total_usuarios=_count(Usuario),
        total_ligas=_count(Liga),
        total_equipos=_count(Equipo),
        total_partidos=_count(Partido),
        total_predicciones=_count(Prediccion),
    )

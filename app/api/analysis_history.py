from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.csv_store import store
from app.db.session import get_db
from app.models.historial_analisis import HistorialAnalisis
from app.models.usuario import Usuario
from app.schemas.historial_analisis import HistorialAnalisisCreate, HistorialAnalisisOut

router = APIRouter(prefix="/analysis-history", tags=["historial"])


def _to_response(item: HistorialAnalisis) -> dict:
    return {
        "id": item.id,
        "partido_id": item.partido_id,
        "categoria": item.categoria,
        "pronostico": item.pronostico,
        "confianza": item.confianza,
        "actualizado_en": item.actualizado_en,
        "partido": store.get_partido(item.partido_id),
    }


@router.get("", response_model=list[HistorialAnalisisOut])
def listar_historial(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> list[dict]:
    """HU-14: historial de analisis consultados por el usuario."""
    stmt = (
        select(HistorialAnalisis)
        .where(HistorialAnalisis.usuario_id == current_user.id)
        .order_by(desc(HistorialAnalisis.actualizado_en))
        .limit(30)
    )
    return [_to_response(item) for item in db.execute(stmt).scalars().all()]


@router.post("", response_model=HistorialAnalisisOut, status_code=status.HTTP_201_CREATED)
def registrar_analisis(
    payload: HistorialAnalisisCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> dict:
    """Registra o refresca una consulta de pronostico para el historial."""
    partido = store.get_partido(payload.partido_id)
    if partido is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    predicciones = store.get_predicciones(payload.partido_id, categoria=payload.categoria)
    if predicciones is None or not predicciones:
        raise HTTPException(status_code=404, detail="Prediccion no disponible")
    prediccion = predicciones[0]

    stmt = select(HistorialAnalisis).where(
        HistorialAnalisis.usuario_id == current_user.id,
        HistorialAnalisis.partido_id == payload.partido_id,
        HistorialAnalisis.categoria == payload.categoria,
    )
    item = db.execute(stmt).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if item is None:
        item = HistorialAnalisis(
            usuario_id=current_user.id,
            partido_id=payload.partido_id,
            categoria=payload.categoria,
            pronostico=prediccion.pronostico,
            confianza=prediccion.confianza,
            creado_en=now,
            actualizado_en=now,
        )
        db.add(item)
    else:
        item.pronostico = prediccion.pronostico
        item.confianza = prediccion.confianza
        item.actualizado_en = now

    db.commit()
    db.refresh(item)
    return _to_response(item)


@router.delete("/{historial_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_historial(
    historial_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> None:
    item = db.get(HistorialAnalisis, historial_id)
    if item is None or item.usuario_id != current_user.id:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    db.delete(item)
    db.commit()

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.partido import Partido
from app.models.prediccion import Prediccion
from app.schemas.stats import (
    ModelPerformanceDetallado,
    PuntoTendencia,
)

router = APIRouter(prefix="/stats", tags=["metricas"])


@router.get("/model-performance", response_model=ModelPerformanceDetallado)
def rendimiento_modelo(db: Session = Depends(get_db)) -> ModelPerformanceDetallado:
    """Panel de aciertos vs fallos del modelo a lo largo del tiempo."""
    stmt = (
        select(Prediccion)
        .join(Partido, Prediccion.partido_id == Partido.id)
        .where(Prediccion.acierto.is_not(None))
        .order_by(Partido.fecha.asc())
    )
    predicciones = list(db.execute(stmt).scalars().all())

    total = len(predicciones)
    aciertos = sum(1 for p in predicciones if p.acierto)
    fallos = total - aciertos
    precision = round(aciertos / total, 4) if total else 0.0

    tendencia: list[PuntoTendencia] = []
    acc_aciertos = acc_total = 0
    for pred in predicciones:
        acc_total += 1
        if pred.acierto:
            acc_aciertos += 1
        fecha = pred.partido.fecha.date().isoformat() if pred.partido else ""
        tendencia.append(
            PuntoTendencia(
                fecha=fecha,
                aciertos=acc_aciertos,
                fallos=acc_total - acc_aciertos,
                precision_acumulada=round(acc_aciertos / acc_total, 4),
            )
        )

    modelo_version = predicciones[-1].modelo_version if predicciones else ""
    return ModelPerformanceDetallado(
        total_evaluadas=total,
        aciertos=aciertos,
        fallos=fallos,
        precision=precision,
        modelo_version=modelo_version,
        tendencia=tendencia,
    )

from fastapi import APIRouter

from app.csv_store import store
from app.schemas.stats import ModelPerformanceDetallado

router = APIRouter(prefix="/stats", tags=["metricas"])


@router.get("/model-performance", response_model=ModelPerformanceDetallado)
def rendimiento_modelo() -> dict:
    """Panel de aciertos vs fallos calculado sobre los partidos finalizados
    de goles.csv (porcentaje de acierto = aciertos / total evaluadas)."""
    return store.get_model_performance()

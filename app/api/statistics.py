from fastapi import APIRouter

from app.csv_store import store
from app.schemas.stats import ModelPerformanceDetallado

router = APIRouter(prefix="/statistics", tags=["estadisticas"])


@router.get("", response_model=ModelPerformanceDetallado)
def estadisticas_publicas() -> dict:
    """Metricas publicas del modelo para el dashboard de visitantes."""
    return store.get_model_performance()

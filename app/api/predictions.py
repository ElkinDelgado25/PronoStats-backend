from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.csv_store import store
from app.schemas.prediccion import PrediccionCategoriaOut, PrediccionOut, PrediccionesPartidoOut

router = APIRouter(tags=["pronosticos"])


@router.get("/predictions", response_model=list[PrediccionOut])
def listar_predicciones(
    league_id: int | None = Query(default=None),
    fecha: date | None = Query(default=None),
    estado: str | None = Query(default=None),
) -> list:
    """Catalogo publico de pronosticos 1X2, con los filtros de /matches."""
    return store.get_predicciones_publicas(
        liga_id=league_id,
        fecha=fecha,
        estado=estado,
    )


@router.get("/matches/{partido_id}/prediction", response_model=PrediccionOut)
def obtener_prediccion(partido_id: int):
    """HU-07, HU-08 y HU-09: pronostico 1X2 con estadisticas y confianza.

    Calculado por el motor de reglas sobre el historial del dataset CSV.
    """
    if store.get_partido(partido_id) is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    pred = store.get_prediccion(partido_id)
    if pred is None:
        raise HTTPException(status_code=404, detail="Prediccion no disponible")
    return pred


@router.get("/matches/{partido_id}/predictions", response_model=PrediccionesPartidoOut)
def obtener_predicciones(
    partido_id: int,
    categoria: str | None = Query(default=None, description="Filtrar por categoria de apuesta"),
):
    """Pronosticos multi-categoria: match_result, total_goals, btts, goal_timing, first_scorer."""
    if store.get_partido(partido_id) is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    preds = store.get_predicciones(partido_id, categoria=categoria)
    if preds is None:
        raise HTTPException(status_code=404, detail="Predicciones no disponibles")
    if categoria is not None and not preds:
        raise HTTPException(status_code=404, detail=f"Categoria '{categoria}' no encontrada")
    return PrediccionesPartidoOut(partido_id=partido_id, predicciones=preds)

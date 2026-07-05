from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.partido import Partido
from app.models.prediccion import Prediccion
from app.schemas.prediccion import FactorPronostico, PrediccionOut
from app.services.prediction_engine import predict_match

router = APIRouter(prefix="/matches", tags=["pronosticos"])


def _persistir_prediccion(db: Session, partido: Partido) -> Prediccion:
    resultado = predict_match(db, partido)
    pred = partido.prediccion or Prediccion(partido_id=partido.id)
    pred.prob_local = resultado.prob_local
    pred.prob_empate = resultado.prob_empate
    pred.prob_visitante = resultado.prob_visitante
    pred.pronostico = resultado.pronostico
    pred.confianza = resultado.confianza
    pred.modelo_version = resultado.modelo_version
    if pred.id is None:
        db.add(pred)
    db.commit()
    db.refresh(pred)
    return pred


@router.get("/{partido_id}/prediction", response_model=PrediccionOut)
def obtener_prediccion(partido_id: int, db: Session = Depends(get_db)) -> PrediccionOut:
    """HU-07, HU-08 y HU-09: pronostico 1X2 con estadisticas y nivel de confianza.

    Si el partido aun no tiene prediccion guardada, la genera y persiste.
    """
    partido = db.get(Partido, partido_id)
    if partido is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    resultado = predict_match(db, partido)
    pred = _persistir_prediccion(db, partido)

    factores = [
        FactorPronostico(
            equipo=partido.local.nombre,
            forma_reciente=round(resultado.forma_local.forma_reciente, 3),
            promedio_goles_favor=round(resultado.forma_local.promedio_goles_favor, 2),
            promedio_goles_contra=round(resultado.forma_local.promedio_goles_contra, 2),
        ),
        FactorPronostico(
            equipo=partido.visitante.nombre,
            forma_reciente=round(resultado.forma_visitante.forma_reciente, 3),
            promedio_goles_favor=round(resultado.forma_visitante.promedio_goles_favor, 2),
            promedio_goles_contra=round(resultado.forma_visitante.promedio_goles_contra, 2),
        ),
    ]

    return PrediccionOut(
        partido_id=partido.id,
        prob_local=pred.prob_local,
        prob_empate=pred.prob_empate,
        prob_visitante=pred.prob_visitante,
        pronostico=pred.pronostico,
        confianza=pred.confianza,
        modelo_version=pred.modelo_version,
        factores=factores,
    )

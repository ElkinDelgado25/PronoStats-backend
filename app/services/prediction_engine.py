from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.partido import Partido
from app.services.team_stats import TeamForm, compute_team_form


@dataclass
class PredictionResult:
    prob_local: float
    prob_empate: float
    prob_visitante: float
    pronostico: str
    confianza: float
    modelo_version: str
    forma_local: TeamForm
    forma_visitante: TeamForm


def _fuerza_ofensiva(forma: TeamForm) -> float:
    """Combina forma reciente y diferencia de goles en un puntaje de fuerza."""
    dif_goles = forma.promedio_goles_favor - forma.promedio_goles_contra
    return forma.forma_reciente + 0.15 * dif_goles


def predict_match(db: Session, partido: Partido) -> PredictionResult:
    """Motor de pronostico basado en reglas (HU-07).

    Combina forma reciente, promedio de goles y ventaja de localia para
    estimar probabilidades 1X2 de forma transparente.
    """
    n = settings.prediction_recent_form_matches
    forma_local = compute_team_form(db, partido.local_id, n)
    forma_visitante = compute_team_form(db, partido.visitante_id, n)

    fuerza_local = _fuerza_ofensiva(forma_local) + settings.prediction_home_advantage
    fuerza_visitante = _fuerza_ofensiva(forma_visitante)

    # Base de empate: mayor cuando las fuerzas estan igualadas.
    diferencia = abs(fuerza_local - fuerza_visitante)
    base_empate = max(0.12, 0.30 - diferencia)

    peso_local = max(fuerza_local, 0.01)
    peso_visitante = max(fuerza_visitante, 0.01)
    total_directo = peso_local + peso_visitante

    restante = 1.0 - base_empate
    prob_local = restante * (peso_local / total_directo)
    prob_visitante = restante * (peso_visitante / total_directo)
    prob_empate = base_empate

    # Normalizacion para garantizar suma = 1.0.
    total = prob_local + prob_empate + prob_visitante
    prob_local /= total
    prob_empate /= total
    prob_visitante /= total

    opciones = {
        "local": prob_local,
        "empate": prob_empate,
        "visitante": prob_visitante,
    }
    pronostico = max(opciones, key=opciones.get)
    confianza = opciones[pronostico]

    return PredictionResult(
        prob_local=round(prob_local, 4),
        prob_empate=round(prob_empate, 4),
        prob_visitante=round(prob_visitante, 4),
        pronostico=pronostico,
        confianza=round(confianza, 4),
        modelo_version=settings.prediction_model_version,
        forma_local=forma_local,
        forma_visitante=forma_visitante,
    )

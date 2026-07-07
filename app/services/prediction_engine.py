from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.partido import Partido
from app.services.agents.match_result import compute_match_result
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


def compute_prediction(
    forma_local: TeamForm,
    forma_visitante: TeamForm,
    home_advantage: float | None = None,
    model_version: str | None = None,
) -> PredictionResult:
    """Nucleo puro del motor de pronostico (HU-07).

    Delega en el agente match_result para mantener compatibilidad con la capa SQLAlchemy.
    """
    if home_advantage is None:
        home_advantage = settings.prediction_home_advantage
    if model_version is None:
        model_version = settings.prediction_model_version

    data = compute_match_result(forma_local, forma_visitante, home_advantage, model_version)
    return PredictionResult(
        prob_local=data.prob_local,
        prob_empate=data.prob_empate,
        prob_visitante=data.prob_visitante,
        pronostico=data.pronostico,
        confianza=data.confianza,
        modelo_version=data.modelo_version,
        forma_local=forma_local,
        forma_visitante=forma_visitante,
    )


def predict_match(db: Session, partido: Partido) -> PredictionResult:
    """Pronostico para un partido almacenado en la BD (capa SQLAlchemy)."""
    n = settings.prediction_recent_form_matches
    forma_local = compute_team_form(db, partido.local_id, n)
    forma_visitante = compute_team_form(db, partido.visitante_id, n)
    return compute_prediction(forma_local, forma_visitante)

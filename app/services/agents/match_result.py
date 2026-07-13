from dataclasses import dataclass

from app.services.agents.base import AgentContext, AgentResult, PredictionAgent, build_form_factors
from app.services.team_stats import TeamForm


@dataclass
class MatchResultData:
    prob_local: float
    prob_empate: float
    prob_visitante: float
    pronostico: str
    confianza: float
    modelo_version: str


def _fuerza_ofensiva(forma: TeamForm) -> float:
    dif_goles = forma.promedio_goles_favor - forma.promedio_goles_contra
    return forma.forma_reciente + 0.15 * dif_goles


def compute_match_result(
    forma_local: TeamForm,
    forma_visitante: TeamForm,
    home_advantage: float,
    model_version: str,
) -> MatchResultData:
    """Nucleo 1X2 extraido del motor original (HU-07)."""
    fuerza_local = _fuerza_ofensiva(forma_local) + home_advantage
    fuerza_visitante = _fuerza_ofensiva(forma_visitante)

    diferencia = abs(fuerza_local - fuerza_visitante)
    base_empate = max(0.12, 0.30 - diferencia)

    peso_local = max(fuerza_local, 0.01)
    peso_visitante = max(fuerza_visitante, 0.01)
    total_directo = peso_local + peso_visitante

    restante = 1.0 - base_empate
    prob_local = restante * (peso_local / total_directo)
    prob_visitante = restante * (peso_visitante / total_directo)
    prob_empate = base_empate

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

    return MatchResultData(
        prob_local=round(prob_local, 4),
        prob_empate=round(prob_empate, 4),
        prob_visitante=round(prob_visitante, 4),
        pronostico=pronostico,
        confianza=round(confianza, 4),
        modelo_version=model_version,
    )


class MatchResultAgent:
    categoria = "match_result"

    def predict(self, ctx: AgentContext) -> AgentResult:
        data = compute_match_result(
            ctx.forma_local,
            ctx.forma_visitante,
            ctx.home_advantage,
            ctx.model_version,
        )
        return AgentResult(
            categoria=self.categoria,
            pronostico=data.pronostico,
            confianza=data.confianza,
            probabilidades={
                "local": data.prob_local,
                "empate": data.prob_empate,
                "visitante": data.prob_visitante,
            },
            modelo_version=data.modelo_version,
            factores=build_form_factors(ctx),
        )


match_result_agent = MatchResultAgent()

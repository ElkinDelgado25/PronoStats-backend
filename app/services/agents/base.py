from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings
from app.services.team_stats import TeamForm

GOAL_HOME_ADVANTAGE = 0.35
OVER_UNDER_LINES = (0.5, 1.5, 2.5, 3.5)
GOAL_TIMING_PERIODS = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90")
GOAL_TIMING_DISTRIBUTION: dict[str, float] = {
    "0-15": 0.22,
    "16-30": 0.18,
    "31-45": 0.20,
    "46-60": 0.15,
    "61-75": 0.13,
    "76-90": 0.12,
}


@dataclass
class AgentContext:
    """Contexto compartido para todos los agentes de prediccion."""

    partido_id: int
    local_nombre: str
    visitante_nombre: str
    forma_local: TeamForm
    forma_visitante: TeamForm
    home_advantage: float = field(default_factory=lambda: settings.prediction_home_advantage)
    model_version: str = field(default_factory=lambda: settings.prediction_model_version)


@dataclass
class AgentResult:
    categoria: str
    pronostico: str
    confianza: float
    probabilidades: dict[str, float]
    modelo_version: str
    factores: list[dict] = field(default_factory=list)


def apply_overround(result: AgentResult, margin: float) -> AgentResult:
    """Aplica el margen comercial (overround) a las probabilidades de una prediccion.

    Aumenta las probabilidades individuales por (1 + overround) y las clampa entre 0.01 y 0.99.
    Mantiene la probabilidad implicita relativa y recalcula la confianza del pronostico.
    """
    adjusted_probs = {}
    for key, val in result.probabilidades.items():
        adjusted_val = val * (1.0 + margin)
        adjusted_probs[key] = round(min(max(adjusted_val, 0.01), 0.99), 4)

    adjusted_confianza = result.confianza
    if result.pronostico in adjusted_probs:
        adjusted_confianza = adjusted_probs[result.pronostico]
    else:
        normalized_pick = result.pronostico.replace(".", "_")
        if normalized_pick in adjusted_probs:
            adjusted_confianza = adjusted_probs[normalized_pick]
        else:
            adjusted_confianza = round(min(max(result.confianza * (1.0 + margin), 0.01), 0.99), 4)

    return AgentResult(
        categoria=result.categoria,
        pronostico=result.pronostico,
        confianza=adjusted_confianza,
        probabilidades=adjusted_probs,
        modelo_version=result.modelo_version,
        factores=result.factores,
    )



class PredictionAgent(Protocol):
    categoria: str

    def predict(self, ctx: AgentContext) -> AgentResult: ...


def poisson_pmf(k: int, lam: float) -> float:
    if k < 0:
        return 0.0
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def expected_goals(ctx: AgentContext) -> tuple[float, float]:
    """Lambda esperada por equipo (Poisson), alineada con generate_dataset.py."""
    lam_local = (
        (ctx.forma_local.promedio_goles_favor + ctx.forma_visitante.promedio_goles_contra) / 2
        + GOAL_HOME_ADVANTAGE
    )
    lam_visitante = (
        ctx.forma_visitante.promedio_goles_favor + ctx.forma_local.promedio_goles_contra
    ) / 2
    return max(lam_local, 0.3), max(lam_visitante, 0.3)


def total_goals_distribution(lam_local: float, lam_visitante: float, max_goals: int = 8) -> list[float]:
    home = [poisson_pmf(k, lam_local) for k in range(max_goals + 1)]
    away = [poisson_pmf(k, lam_visitante) for k in range(max_goals + 1)]
    max_total = max_goals * 2
    dist = [0.0] * (max_total + 1)
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            dist[h + a] += home[h] * away[a]
    total = sum(dist)
    if total > 0:
        dist = [p / total for p in dist]
    return dist


def prob_over_line(dist: list[float], line: float) -> float:
    threshold = int(line + 0.5)
    return sum(dist[threshold:])


def build_form_factors(ctx: AgentContext) -> list[dict]:
    return [
        {
            "equipo": ctx.local_nombre,
            "forma_reciente": round(ctx.forma_local.forma_reciente, 3),
            "promedio_goles_favor": round(ctx.forma_local.promedio_goles_favor, 2),
            "promedio_goles_contra": round(ctx.forma_local.promedio_goles_contra, 2),
        },
        {
            "equipo": ctx.visitante_nombre,
            "forma_reciente": round(ctx.forma_visitante.forma_reciente, 3),
            "promedio_goles_favor": round(ctx.forma_visitante.promedio_goles_favor, 2),
            "promedio_goles_contra": round(ctx.forma_visitante.promedio_goles_contra, 2),
        },
    ]

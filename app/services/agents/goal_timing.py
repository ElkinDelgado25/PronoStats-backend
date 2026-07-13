from app.services.agents.base import (
    GOAL_TIMING_DISTRIBUTION,
    GOAL_TIMING_PERIODS,
    AgentContext,
    AgentResult,
    expected_goals,
)


class GoalTimingAgent:
    """Distribucion de goles por periodo usando heuristica fija de liga."""

    categoria = "goal_timing"

    def predict(self, ctx: AgentContext) -> AgentResult:
        lam_local, lam_visitante = expected_goals(ctx)
        lam_total = lam_local + lam_visitante

        total_share = sum(GOAL_TIMING_DISTRIBUTION.values())
        proporciones = {
            periodo: round(GOAL_TIMING_DISTRIBUTION[periodo] / total_share, 4)
            for periodo in GOAL_TIMING_PERIODS
        }

        pronostico = max(proporciones, key=proporciones.get)
        confianza = proporciones[pronostico]

        return AgentResult(
            categoria=self.categoria,
            pronostico=pronostico,
            confianza=confianza,
            probabilidades=proporciones,
            modelo_version=f"{ctx.model_version}-heuristic",
            factores=[
                {
                    "lambda_total_esperada": round(lam_total, 3),
                    "nota": "Distribucion fija por periodo (sin minutos reales en el dataset)",
                },
            ],
        )


goal_timing_agent = GoalTimingAgent()

from app.services.agents.base import (
    OVER_UNDER_LINES,
    AgentContext,
    AgentResult,
    expected_goals,
    prob_over_line,
    total_goals_distribution,
)


class TotalGoalsAgent:
    categoria = "total_goals"

    def predict(self, ctx: AgentContext) -> AgentResult:
        lam_local, lam_visitante = expected_goals(ctx)
        dist = total_goals_distribution(lam_local, lam_visitante)

        probabilidades: dict[str, float] = {}
        for line in OVER_UNDER_LINES:
            over = round(prob_over_line(dist, line), 4)
            under = round(1.0 - over, 4)
            key = str(line).replace(".", "_")
            probabilidades[f"over_{key}"] = over
            probabilidades[f"under_{key}"] = under

        # Linea 2.5 como pronostico principal (apuesta mas comun).
        over_25 = probabilidades["over_2_5"]
        under_25 = probabilidades["under_2_5"]
        if over_25 >= under_25:
            pronostico = "over_2.5"
            confianza = over_25
        else:
            pronostico = "under_2.5"
            confianza = under_25

        return AgentResult(
            categoria=self.categoria,
            pronostico=pronostico,
            confianza=confianza,
            probabilidades=probabilidades,
            modelo_version=f"{ctx.model_version}-poisson",
            factores=[
                {"lambda_local": round(lam_local, 3), "lambda_visitante": round(lam_visitante, 3)},
            ],
        )


total_goals_agent = TotalGoalsAgent()

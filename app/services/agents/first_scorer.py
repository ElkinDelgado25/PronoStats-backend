import math

from app.services.agents.base import AgentContext, AgentResult, expected_goals


class FirstScorerAgent:
    """Primer gol a nivel equipo (local vs visitante). Sin datos de jugadores."""

    categoria = "first_scorer"

    def predict(self, ctx: AgentContext) -> AgentResult:
        lam_local, lam_visitante = expected_goals(ctx)
        lam_total = lam_local + lam_visitante

        p_sin_goles = round(math.exp(-lam_total), 4) if lam_total > 0 else 1.0
        if lam_total > 0:
            share_local = lam_local / lam_total
            share_visitante = lam_visitante / lam_total
            p_local = round(share_local * (1.0 - p_sin_goles), 4)
            p_visitante = round(share_visitante * (1.0 - p_sin_goles), 4)
        else:
            p_local = p_visitante = 0.0

        opciones = {
            "local": p_local,
            "visitante": p_visitante,
            "sin_goles": p_sin_goles,
        }
        pronostico = max(opciones, key=opciones.get)
        confianza = opciones[pronostico]

        return AgentResult(
            categoria=self.categoria,
            pronostico=pronostico,
            confianza=confianza,
            probabilidades=opciones,
            modelo_version=f"{ctx.model_version}-poisson",
            factores=[
                {"lambda_local": round(lam_local, 3), "lambda_visitante": round(lam_visitante, 3)},
            ],
        )


first_scorer_agent = FirstScorerAgent()

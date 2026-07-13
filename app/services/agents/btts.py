import math

from app.services.agents.base import AgentContext, AgentResult, expected_goals


class BttsAgent:
    categoria = "btts"

    def predict(self, ctx: AgentContext) -> AgentResult:
        lam_local, lam_visitante = expected_goals(ctx)

        p_local_marca = 1.0 - math.exp(-lam_local)
        p_visitante_marca = 1.0 - math.exp(-lam_visitante)
        p_si = round(p_local_marca * p_visitante_marca, 4)
        p_no = round(1.0 - p_si, 4)

        if p_si >= p_no:
            pronostico = "si"
            confianza = p_si
        else:
            pronostico = "no"
            confianza = p_no

        return AgentResult(
            categoria=self.categoria,
            pronostico=pronostico,
            confianza=confianza,
            probabilidades={"si": p_si, "no": p_no},
            modelo_version=f"{ctx.model_version}-poisson",
            factores=[
                {
                    "p_local_marca": round(p_local_marca, 4),
                    "p_visitante_marca": round(p_visitante_marca, 4),
                },
            ],
        )


btts_agent = BttsAgent()

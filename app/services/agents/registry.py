from app.services.agents.base import AgentContext, AgentResult, PredictionAgent
from app.services.agents.btts import btts_agent
from app.services.agents.first_scorer import first_scorer_agent
from app.services.agents.goal_timing import goal_timing_agent
from app.services.agents.match_result import match_result_agent
from app.services.agents.total_goals import total_goals_agent

AGENTS: list[PredictionAgent] = [
    match_result_agent,
    total_goals_agent,
    btts_agent,
    goal_timing_agent,
    first_scorer_agent,
]

_AGENTS_BY_CATEGORIA: dict[str, PredictionAgent] = {a.categoria: a for a in AGENTS}


def get_agent(categoria: str) -> PredictionAgent | None:
    return _AGENTS_BY_CATEGORIA.get(categoria)


def run_all_agents(ctx: AgentContext) -> dict[str, AgentResult]:
    return {agent.categoria: agent.predict(ctx) for agent in AGENTS}

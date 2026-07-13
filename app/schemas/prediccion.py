from pydantic import BaseModel


class FactorPronostico(BaseModel):
    """Detalle transparente de las estadisticas usadas por el modelo (HU-08)."""

    equipo: str
    forma_reciente: float
    promedio_goles_favor: float
    promedio_goles_contra: float


class PrediccionOut(BaseModel):
    partido_id: int
    prob_local: float
    prob_empate: float
    prob_visitante: float
    pronostico: str
    confianza: float
    modelo_version: str
    factores: list[FactorPronostico] = []

    model_config = {"from_attributes": True}


class FactorGenerico(BaseModel):
    """Factores adicionales devueltos por agentes no-1X2."""

    model_config = {"extra": "allow"}


class PrediccionCategoriaOut(BaseModel):
    categoria: str
    pronostico: str
    confianza: float
    probabilidades: dict[str, float]
    modelo_version: str
    factores: list[dict] = []

    model_config = {"from_attributes": True}


class PrediccionesPartidoOut(BaseModel):
    partido_id: int
    predicciones: list[PrediccionCategoriaOut]

    model_config = {"from_attributes": True}

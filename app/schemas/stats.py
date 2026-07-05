from pydantic import BaseModel


class ModelPerformance(BaseModel):
    total_evaluadas: int
    aciertos: int
    fallos: int
    precision: float
    modelo_version: str


class PuntoTendencia(BaseModel):
    fecha: str
    aciertos: int
    fallos: int
    precision_acumulada: float


class ModelPerformanceDetallado(ModelPerformance):
    tendencia: list[PuntoTendencia] = []


class UsageStats(BaseModel):
    total_usuarios: int
    total_ligas: int
    total_equipos: int
    total_partidos: int
    total_predicciones: int

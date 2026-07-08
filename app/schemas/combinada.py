from enum import Enum

from pydantic import BaseModel, Field


class TipoCombinada(str, Enum):
    individual = "individual"
    multiple = "multiple"
    sistema = "sistema"


class SeleccionCombinadaIn(BaseModel):
    partido_id: int
    categoria: str = Field(
        description="match_result | total_goals | btts | goal_timing | first_scorer | double_chance"
    )
    seleccion: str = Field(description="Clave dentro de probabilidades, ej. local, over_2_5, si")


class CombinadaCalcularIn(BaseModel):
    tipo: TipoCombinada
    selecciones: list[SeleccionCombinadaIn] = Field(min_length=1, max_length=20)
    importe: float = Field(default=0, ge=0, description="Importe por apuesta individual o multiple")
    importe_por_combinacion: float = Field(
        default=0, ge=0, description="Importe por cada sub-combinacion en tipo sistema"
    )
    sistema_k: int | None = Field(
        default=None,
        ge=2,
        description="Tamano de cada sub-combinacion en sistema (ej. 2 para '2 de 3')",
    )


class SeleccionCombinadaOut(BaseModel):
    partido_id: int
    partido: str
    fecha: str
    categoria: str
    categoria_label: str
    seleccion: str
    seleccion_label: str
    probabilidad: float
    cuota: float
    liga_pais: str = ""
    escudo_url: str | None = None
    local_escudo_url: str | None = None
    visitante_escudo_url: str | None = None


class SubCombinadaOut(BaseModel):
    selecciones: list[SeleccionCombinadaOut]
    cuota: float
    probabilidad: float
    importe: float
    ganancia_potencial: float


class CombinadaCalcularOut(BaseModel):
    tipo: TipoCombinada
    selecciones: list[SeleccionCombinadaOut]
    cuota_combinada: float | None = None
    probabilidad_combinada: float | None = None
    num_pronosticos: int
    valor_total: float
    ganancia_potencial: float
    sub_combinaciones: list[SubCombinadaOut] = []
    advertencias: list[str] = []


class MercadoOut(BaseModel):
    categoria: str
    label: str
    selecciones: list[dict[str, str]]

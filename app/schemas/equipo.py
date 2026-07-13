from pydantic import BaseModel, Field


class EquipoBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    liga_id: int
    escudo_url: str | None = Field(default=None, max_length=500)


class EquipoCreate(EquipoBase):
    pass


class EquipoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    liga_id: int | None = None
    escudo_url: str | None = Field(default=None, max_length=500)


class EquipoOut(EquipoBase):
    id: int

    model_config = {"from_attributes": True}


class EquipoStats(BaseModel):
    equipo_id: int
    nombre: str
    partidos_jugados: int
    victorias: int
    empates: int
    derrotas: int
    goles_favor: int
    goles_contra: int
    promedio_goles_favor: float
    promedio_goles_contra: float
    forma_reciente: float


class ComparacionResumen(BaseModel):
    mejor_forma: str
    mejor_ataque: str
    mejor_defensa: str
    ventaja_general: str


class EquipoComparacionOut(BaseModel):
    equipo_a: EquipoStats
    equipo_b: EquipoStats
    enfrentamientos_directos: dict
    resumen: ComparacionResumen

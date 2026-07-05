from datetime import datetime

from pydantic import BaseModel, Field

from app.models.partido import EstadoPartido
from app.schemas.equipo import EquipoOut


class PartidoBase(BaseModel):
    liga_id: int
    local_id: int
    visitante_id: int
    fecha: datetime


class PartidoCreate(PartidoBase):
    pass


class PartidoUpdate(BaseModel):
    liga_id: int | None = None
    local_id: int | None = None
    visitante_id: int | None = None
    fecha: datetime | None = None
    estado: EstadoPartido | None = None


class ResultadoIn(BaseModel):
    goles_local: int = Field(ge=0)
    goles_visitante: int = Field(ge=0)


class ResultadoOut(BaseModel):
    goles_local: int
    goles_visitante: int
    ganador: str

    model_config = {"from_attributes": True}


class PartidoOut(BaseModel):
    id: int
    liga_id: int
    fecha: datetime
    estado: EstadoPartido
    local: EquipoOut
    visitante: EquipoOut
    resultado: ResultadoOut | None = None

    model_config = {"from_attributes": True}


class EnfrentamientoH2H(BaseModel):
    total_partidos: int
    victorias_local: int
    empates: int
    victorias_visitante: int
    historial: list[PartidoOut]

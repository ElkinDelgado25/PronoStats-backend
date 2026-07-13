from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.partido import PartidoOut


class HistorialAnalisisCreate(BaseModel):
    partido_id: int = Field(gt=0)
    categoria: str = Field(default="match_result", min_length=2, max_length=60)


class HistorialAnalisisOut(BaseModel):
    id: int
    partido_id: int
    categoria: str
    pronostico: str
    confianza: float
    actualizado_en: datetime
    partido: PartidoOut | None = None

    model_config = {"from_attributes": True}

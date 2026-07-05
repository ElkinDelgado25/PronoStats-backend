from pydantic import BaseModel

from app.schemas.equipo import EquipoOut


class FavoritoCreate(BaseModel):
    equipo_id: int


class FavoritoOut(BaseModel):
    id: int
    equipo: EquipoOut

    model_config = {"from_attributes": True}

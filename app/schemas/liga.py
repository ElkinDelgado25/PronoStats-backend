from pydantic import BaseModel, Field


class LigaBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    pais: str = Field(min_length=2, max_length=80)
    temporada: str = Field(min_length=2, max_length=20)


class LigaCreate(LigaBase):
    pass


class LigaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    pais: str | None = Field(default=None, min_length=2, max_length=80)
    temporada: str | None = Field(default=None, min_length=2, max_length=20)


class LigaOut(LigaBase):
    id: int
    escudo_url: str | None = None

    model_config = {"from_attributes": True}

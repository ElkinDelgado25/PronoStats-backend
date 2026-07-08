from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.models.boleto import EstadoBoleto
from app.schemas.combinada import SeleccionCombinadaIn, TipoCombinada


class BoletoCrearIn(BaseModel):
    tipo: TipoCombinada
    selecciones: list[SeleccionCombinadaIn] = Field(min_length=1, max_length=20)
    importe: float = Field(gt=0)
    importe_por_combinacion: float | None = Field(default=None, ge=0)
    sistema_k: int | None = Field(default=None, ge=2)


class BoletoOut(BaseModel):
    uuid: str
    tipo: str
    estado: EstadoBoleto
    importe: float
    valor_total: float
    cuota_combinada: float | None
    ganancia_potencial: float
    ganancia_real: float | None
    num_pronosticos: int
    selecciones: list
    advertencias: list | None
    detalle_liquidacion: dict | None
    creado_en: datetime
    liquidado_en: datetime | None

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def codigo_pronostico(self) -> str:
        return f"PRN-{self.uuid.replace('-', '')[:8].upper()}"


class BoletoConsultaOut(BoletoOut):
    mensaje_estado: str = ""


class DepositoIn(BaseModel):
    monto: float = Field(gt=0, le=10000)
    metodo: str = Field(default="mock", description="mock | stripe (futuro)")


class MovimientoOut(BaseModel):
    id: int
    tipo: str
    monto: float
    saldo_despues: float
    descripcion: str
    metodo_pago: str | None
    boleto_uuid: str | None
    creado_en: datetime

    model_config = {"from_attributes": True}


class CarteraOut(BaseModel):
    saldo: float
    movimientos: list[MovimientoOut] = []

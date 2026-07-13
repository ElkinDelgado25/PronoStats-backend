from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from app.models.boleto import EstadoBoleto
from app.schemas.combinada import SeleccionCombinadaIn, TipoCombinada


class BoletoCrearIn(BaseModel):
    tipo: TipoCombinada
    selecciones: list[SeleccionCombinadaIn] = Field(min_length=1, max_length=20)
    importe: float = Field(gt=0)
    importe_por_combinacion: float | None = Field(default=None, ge=0)
    sistema_k: int | None = Field(default=None, ge=2)


class BoletoReclamarIn(BaseModel):
    uuids: list[str] = Field(min_length=1, max_length=50)


class BoletoOut(BaseModel):
    uuid: str
    tipo: str
    estado: EstadoBoleto
    pagado: bool = True
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
    mensaje: str | None = None

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def codigo_pronostico(self) -> str:
        return f"PRN-{self.uuid.replace('-', '')[:8].upper()}"


class BoletoConsultaOut(BoletoOut):
    mensaje_estado: str = ""


class DepositoIn(BaseModel):
    monto: float = Field(gt=0, le=10000)
    metodo: str = Field(default="mock", description="mock | stripe (solo mock directo; stripe usa checkout)")


class StripeCheckoutIn(BaseModel):
    monto: float = Field(gt=0, le=10000)


class StripeCheckoutOut(BaseModel):
    url: str
    session_id: str


class StripeConfirmIn(BaseModel):
    session_id: str = Field(min_length=3, max_length=120)


class StripeConfirmOut(BaseModel):
    monto: float
    saldo_despues: float
    ya_acreditado: bool
    mensaje: str


class StripeStatusOut(BaseModel):
    configurado: bool
    webhook_configurado: bool
    confirm_fallback: bool
    moneda: str
    deposito_minimo: float


class RecargaIn(BaseModel):
    """Solicitud de recarga desde la pantalla de cartera."""

    amount: float = Field(ge=5, le=500)
    payment_method: Literal["stripe", "transfer", "mock"]


class RecargaOut(BaseModel):
    status: Literal["pending", "success", "error"]
    redirect_url: str | None = None
    message: str


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

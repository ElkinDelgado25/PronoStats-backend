import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.usuario import Usuario


class EstadoBoleto(str, enum.Enum):
    pendiente = "pendiente"
    ganado = "ganado"
    perdido = "perdido"
    parcial = "parcial"
    cancelado = "cancelado"


class Boleto(Base):
    __tablename__ = "boletos"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    estado: Mapped[EstadoBoleto] = mapped_column(
        Enum(EstadoBoleto), default=EstadoBoleto.pendiente, nullable=False
    )
    importe: Mapped[float] = mapped_column(Float, nullable=False)
    valor_total: Mapped[float] = mapped_column(Float, nullable=False)
    cuota_combinada: Mapped[float | None] = mapped_column(Float, nullable=True)
    ganancia_potencial: Mapped[float] = mapped_column(Float, nullable=False)
    ganancia_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    sistema_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_pronosticos: Mapped[int] = mapped_column(Integer, default=1)
    selecciones: Mapped[list] = mapped_column(JSON, nullable=False)
    sub_combinaciones: Mapped[list | None] = mapped_column(JSON, nullable=True)
    advertencias: Mapped[list | None] = mapped_column(JSON, nullable=True)
    detalle_liquidacion: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    liquidado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="boletos")

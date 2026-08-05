import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.usuario import Usuario


class TipoMovimiento(str, enum.Enum):
    deposito = "deposito"
    apuesta = "apuesta"
    premio = "premio"
    ajuste = "ajuste"


class MetodoPago(str, enum.Enum):
    mock = "mock"
    stripe = "stripe"
    transfer = "transfer"


class Cartera(Base):
    __tablename__ = "carteras"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), unique=True, index=True, nullable=False
    )
    saldo: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="cartera")
    movimientos: Mapped[list["MovimientoCartera"]] = relationship(
        back_populates="cartera", cascade="all, delete-orphan"
    )


class MovimientoCartera(Base):
    __tablename__ = "movimientos_cartera"
    __table_args__ = (
        UniqueConstraint(
            "referencia_externa",
            name="uq_movimientos_cartera_referencia_externa",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cartera_id: Mapped[int] = mapped_column(ForeignKey("carteras.id"), index=True)
    tipo: Mapped[TipoMovimiento] = mapped_column(Enum(TipoMovimiento), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    saldo_despues: Mapped[float] = mapped_column(Float, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    metodo_pago: Mapped[MetodoPago | None] = mapped_column(Enum(MetodoPago), nullable=True)
    referencia_externa: Mapped[str | None] = mapped_column(String(120), nullable=True)
    boleto_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    cartera: Mapped["Cartera"] = relationship(back_populates="movimientos")

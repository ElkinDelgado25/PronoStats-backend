from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.usuario import Usuario


class HistorialAnalisis(Base):
    __tablename__ = "historial_analisis"
    __table_args__ = (
        UniqueConstraint(
            "usuario_id",
            "partido_id",
            "categoria",
            name="uq_usuario_partido_categoria",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False, index=True
    )
    partido_id: Mapped[int] = mapped_column(nullable=False, index=True)
    categoria: Mapped[str] = mapped_column(String(60), nullable=False)
    pronostico: Mapped[str] = mapped_column(String(80), nullable=False)
    confianza: Mapped[float] = mapped_column(Float, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="historial_analisis")

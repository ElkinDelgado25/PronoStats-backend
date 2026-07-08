from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.partido import Partido


class Prediccion(Base):
    __tablename__ = "predicciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    partido_id: Mapped[int] = mapped_column(
        ForeignKey("partidos.id"), nullable=False, unique=True, index=True
    )
    prob_local: Mapped[float] = mapped_column(Float, nullable=False)
    prob_empate: Mapped[float] = mapped_column(Float, nullable=False)
    prob_visitante: Mapped[float] = mapped_column(Float, nullable=False)
    # Resultado predicho (1X2): 'local' | 'empate' | 'visitante'.
    pronostico: Mapped[str] = mapped_column(String(20), nullable=False)
    # Confianza = probabilidad del resultado elegido.
    confianza: Mapped[float] = mapped_column(Float, nullable=False)
    modelo_version: Mapped[str] = mapped_column(String(40), nullable=False)
    # Evaluacion contra el resultado real (None mientras el partido no finaliza).
    acierto: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    partido: Mapped["Partido"] = relationship(back_populates="prediccion")

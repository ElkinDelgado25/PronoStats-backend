import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EstadoPartido(str, enum.Enum):
    programado = "programado"
    finalizado = "finalizado"


class Partido(Base):
    __tablename__ = "partidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    liga_id: Mapped[int] = mapped_column(ForeignKey("ligas.id"), nullable=False, index=True)
    local_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"), nullable=False)
    visitante_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"), nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    estado: Mapped[EstadoPartido] = mapped_column(
        Enum(EstadoPartido), default=EstadoPartido.programado, nullable=False
    )

    liga: Mapped["Liga"] = relationship(back_populates="partidos")
    local: Mapped["Equipo"] = relationship(foreign_keys=[local_id])
    visitante: Mapped["Equipo"] = relationship(foreign_keys=[visitante_id])
    resultado: Mapped["Resultado | None"] = relationship(
        back_populates="partido", uselist=False, cascade="all, delete-orphan"
    )
    prediccion: Mapped["Prediccion | None"] = relationship(
        back_populates="partido", uselist=False, cascade="all, delete-orphan"
    )

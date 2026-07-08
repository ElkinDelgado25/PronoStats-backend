from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.equipo import Equipo
    from app.models.partido import Partido


class Liga(Base):
    __tablename__ = "ligas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    pais: Mapped[str] = mapped_column(String(80), nullable=False)
    temporada: Mapped[str] = mapped_column(String(20), nullable=False)

    equipos: Mapped[list["Equipo"]] = relationship(
        back_populates="liga", cascade="all, delete-orphan"
    )
    partidos: Mapped[list["Partido"]] = relationship(
        back_populates="liga", cascade="all, delete-orphan"
    )

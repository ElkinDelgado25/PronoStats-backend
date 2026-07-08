import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.boleto import Boleto
    from app.models.cartera import Cartera
    from app.models.favorito import Favorito
    from app.models.historial_analisis import HistorialAnalisis


class RolUsuario(str, enum.Enum):
    usuario = "usuario"
    admin = "admin"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(
        Enum(RolUsuario), default=RolUsuario.usuario, nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    favoritos: Mapped[list["Favorito"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )
    historial_analisis: Mapped[list["HistorialAnalisis"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )
    cartera: Mapped["Cartera | None"] = relationship(
        back_populates="usuario", uselist=False, cascade="all, delete-orphan"
    )
    boletos: Mapped[list["Boleto"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )

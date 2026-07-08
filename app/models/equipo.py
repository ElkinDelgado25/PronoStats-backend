from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.liga import Liga


class Equipo(Base):
    __tablename__ = "equipos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    escudo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    liga_id: Mapped[int] = mapped_column(ForeignKey("ligas.id"), nullable=False, index=True)

    liga: Mapped["Liga"] = relationship(back_populates="equipos")

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Resultado(Base):
    __tablename__ = "resultados"

    partido_id: Mapped[int] = mapped_column(
        ForeignKey("partidos.id"), primary_key=True
    )
    goles_local: Mapped[int] = mapped_column(Integer, nullable=False)
    goles_visitante: Mapped[int] = mapped_column(Integer, nullable=False)

    partido: Mapped["Partido"] = relationship(back_populates="resultado")

    @property
    def ganador(self) -> str:
        """Resultado 1X2: 'local', 'empate' o 'visitante'."""
        if self.goles_local > self.goles_visitante:
            return "local"
        if self.goles_local < self.goles_visitante:
            return "visitante"
        return "empate"

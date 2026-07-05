from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.partido import EstadoPartido, Partido


@dataclass
class TeamForm:
    equipo_id: int
    partidos_jugados: int
    victorias: int
    empates: int
    derrotas: int
    goles_favor: int
    goles_contra: int

    @property
    def promedio_goles_favor(self) -> float:
        return self.goles_favor / self.partidos_jugados if self.partidos_jugados else 0.0

    @property
    def promedio_goles_contra(self) -> float:
        return self.goles_contra / self.partidos_jugados if self.partidos_jugados else 0.0

    @property
    def forma_reciente(self) -> float:
        """Puntos por partido normalizados a [0, 1] (victoria=3, empate=1)."""
        if not self.partidos_jugados:
            return 0.5
        puntos = self.victorias * 3 + self.empates
        return puntos / (self.partidos_jugados * 3)


def _finished_matches_for_team(db: Session, equipo_id: int, limit: int) -> list[Partido]:
    stmt = (
        select(Partido)
        .where(
            Partido.estado == EstadoPartido.finalizado,
            or_(Partido.local_id == equipo_id, Partido.visitante_id == equipo_id),
        )
        .order_by(Partido.fecha.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def compute_team_form(db: Session, equipo_id: int, limit: int) -> TeamForm:
    partidos = _finished_matches_for_team(db, equipo_id, limit)
    victorias = empates = derrotas = goles_favor = goles_contra = 0

    for p in partidos:
        if p.resultado is None:
            continue
        es_local = p.local_id == equipo_id
        gf = p.resultado.goles_local if es_local else p.resultado.goles_visitante
        gc = p.resultado.goles_visitante if es_local else p.resultado.goles_local
        goles_favor += gf
        goles_contra += gc
        if gf > gc:
            victorias += 1
        elif gf == gc:
            empates += 1
        else:
            derrotas += 1

    jugados = victorias + empates + derrotas
    return TeamForm(
        equipo_id=equipo_id,
        partidos_jugados=jugados,
        victorias=victorias,
        empates=empates,
        derrotas=derrotas,
        goles_favor=goles_favor,
        goles_contra=goles_contra,
    )

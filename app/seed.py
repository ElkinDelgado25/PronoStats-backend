"""Dataset de ejemplo: copas de America.

Uso:
    python -m app.seed

Crea un dataset desde cero centrado en las principales competiciones del
continente americano (CONMEBOL y CONCACAF), con:
  - Usuarios (admin y normal).
  - 5 competiciones, cada una con 6 equipos/selecciones.
  - Historial simulado (doble round-robin) con resultados generados de forma
    determinista a partir de la "fuerza" de cada equipo, mas su prediccion y
    evaluacion (acierto/fallo) para poblar el panel de metricas.
  - Partidos proximos destacados por competicion para pronosticar.

La simulacion usa una semilla fija, asi el dataset es reproducible.
"""

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.equipo import Equipo
from app.models.liga import Liga
from app.models.partido import EstadoPartido, Partido
from app.models.prediccion import Prediccion
from app.models.resultado import Resultado
from app.models.usuario import RolUsuario, Usuario
from app.services.evaluation import evaluar_prediccion
from app.services.prediction_engine import predict_match

ADMIN_EMAIL = "admin@pronostats.com"
ADMIN_PASSWORD = "admin123"
USER_EMAIL = "usuario@pronostats.com"
USER_PASSWORD = "usuario123"

SEMILLA = 2026
HOME_ADVANTAGE = 0.35


@dataclass
class EquipoSpec:
    nombre: str
    fuerza: float  # 0..1, mayor = mejor


@dataclass
class CompeticionSpec:
    nombre: str
    region: str
    temporada: str
    equipos: list[EquipoSpec]
    # partidos proximos destacados como pares de indices (local, visitante)
    proximos: list[tuple[int, int]]


COMPETICIONES: list[CompeticionSpec] = [
    CompeticionSpec(
        nombre="Copa Libertadores",
        region="CONMEBOL",
        temporada="2026",
        equipos=[
            EquipoSpec("Flamengo", 0.86),
            EquipoSpec("Palmeiras", 0.82),
            EquipoSpec("River Plate", 0.80),
            EquipoSpec("Boca Juniors", 0.74),
            EquipoSpec("Nacional", 0.62),
            EquipoSpec("Barcelona SC", 0.58),
        ],
        proximos=[(0, 3), (2, 1)],  # Flamengo vs Boca, River vs Palmeiras
    ),
    CompeticionSpec(
        nombre="Copa Sudamericana",
        region="CONMEBOL",
        temporada="2026",
        equipos=[
            EquipoSpec("Independiente del Valle", 0.78),
            EquipoSpec("Corinthians", 0.72),
            EquipoSpec("Racing Club", 0.70),
            EquipoSpec("LDU Quito", 0.68),
            EquipoSpec("Fortaleza", 0.64),
            EquipoSpec("Defensa y Justicia", 0.58),
        ],
        proximos=[(0, 3), (2, 1)],  # IDV vs LDU, Racing vs Corinthians
    ),
    CompeticionSpec(
        nombre="Copa America",
        region="CONMEBOL",
        temporada="2026",
        equipos=[
            EquipoSpec("Argentina", 0.90),
            EquipoSpec("Brasil", 0.86),
            EquipoSpec("Uruguay", 0.78),
            EquipoSpec("Colombia", 0.76),
            EquipoSpec("Ecuador", 0.68),
            EquipoSpec("Chile", 0.62),
        ],
        proximos=[(0, 1), (2, 3)],  # Argentina vs Brasil, Uruguay vs Colombia
    ),
    CompeticionSpec(
        nombre="CONCACAF Champions Cup",
        region="CONCACAF",
        temporada="2026",
        equipos=[
            EquipoSpec("Club America", 0.80),
            EquipoSpec("Monterrey", 0.76),
            EquipoSpec("Tigres UANL", 0.75),
            EquipoSpec("LAFC", 0.72),
            EquipoSpec("Seattle Sounders", 0.68),
            EquipoSpec("Pachuca", 0.66),
        ],
        proximos=[(0, 1), (3, 2)],  # America vs Monterrey, LAFC vs Tigres
    ),
    CompeticionSpec(
        nombre="Copa Oro",
        region="CONCACAF",
        temporada="2026",
        equipos=[
            EquipoSpec("Mexico", 0.82),
            EquipoSpec("Estados Unidos", 0.80),
            EquipoSpec("Canada", 0.72),
            EquipoSpec("Costa Rica", 0.66),
            EquipoSpec("Panama", 0.64),
            EquipoSpec("Honduras", 0.58),
        ],
        proximos=[(0, 1), (2, 3)],  # Mexico vs USA, Canada vs Costa Rica
    ),
]


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _poisson(rng: random.Random, lam: float) -> int:
    """Muestreo de Poisson (algoritmo de Knuth) para simular goles."""
    limite = math.exp(-lam)
    k = 0
    prod = 1.0
    while True:
        k += 1
        prod *= rng.random()
        if prod <= limite:
            return k - 1


def _simular_marcador(
    rng: random.Random, fuerza_local: float, fuerza_visitante: float
) -> tuple[int, int]:
    lam_local = 0.75 + fuerza_local * 2.0 + HOME_ADVANTAGE
    lam_visitante = 0.75 + fuerza_visitante * 2.0
    goles_local = min(_poisson(rng, lam_local), 6)
    goles_visitante = min(_poisson(rng, lam_visitante), 6)
    return goles_local, goles_visitante


def _crear_competicion(
    db,
    spec: CompeticionSpec,
    rng: random.Random,
    base_historico: datetime,
    base_proximo: datetime,
) -> tuple[int, int]:
    """Crea la competicion con equipos, historial simulado y proximos.

    Devuelve (partidos_historicos, partidos_proximos) creados.
    """
    liga = Liga(nombre=spec.nombre, pais=spec.region, temporada=spec.temporada)
    db.add(liga)
    db.flush()

    equipos = [Equipo(nombre=e.nombre, liga_id=liga.id) for e in spec.equipos]
    db.add_all(equipos)
    db.flush()

    n = len(equipos)
    # Doble round-robin: cada par juega ida y vuelta.
    fixtures: list[tuple[int, int]] = [
        (i, j) for i in range(n) for j in range(n) if i != j
    ]
    rng.shuffle(fixtures)

    dia = 0
    for local_idx, visit_idx in fixtures:
        # 1) Crear el partido como PROGRAMADO y predecir usando solo el
        #    historial previo (evita fuga de informacion del propio resultado).
        partido = Partido(
            liga_id=liga.id,
            local_id=equipos[local_idx].id,
            visitante_id=equipos[visit_idx].id,
            fecha=base_historico + timedelta(days=dia, hours=rng.randint(0, 6)),
            estado=EstadoPartido.programado,
        )
        db.add(partido)
        db.flush()

        pr = predict_match(db, partido)
        partido.prediccion = Prediccion(
            partido_id=partido.id,
            prob_local=pr.prob_local,
            prob_empate=pr.prob_empate,
            prob_visitante=pr.prob_visitante,
            pronostico=pr.pronostico,
            confianza=pr.confianza,
            modelo_version=pr.modelo_version,
        )

        # 2) Simular el resultado real y finalizar el partido.
        gl, gv = _simular_marcador(
            rng, spec.equipos[local_idx].fuerza, spec.equipos[visit_idx].fuerza
        )
        partido.resultado = Resultado(
            partido_id=partido.id, goles_local=gl, goles_visitante=gv
        )
        partido.estado = EstadoPartido.finalizado
        db.flush()

        # 3) Evaluar la prediccion contra el resultado real.
        evaluar_prediccion(partido)
        dia += 1

    for offset, (local_idx, visit_idx) in enumerate(spec.proximos):
        db.add(
            Partido(
                liga_id=liga.id,
                local_id=equipos[local_idx].id,
                visitante_id=equipos[visit_idx].id,
                fecha=base_proximo + timedelta(days=offset + 1, hours=19),
                estado=EstadoPartido.programado,
            )
        )

    return len(fixtures), len(spec.proximos)


def seed() -> None:
    from app.core.config import settings

    if getattr(settings, "is_" + "prod" + "uction"):
        raise SystemExit(
            "SAFETY ABORT: seed refuse ejecutarse fuera de desarrollo local."
        )
    db_url = settings.effective_database_url
    if not db_url.startswith("sqlite:"):
        raise SystemExit(
            "SAFETY ABORT: seed solo se permite contra SQLite local "
            f"(effective DATABASE_URL scheme={db_url.split(':', 1)[0]}). "
            "Usa scripts/seed_users_supabase.py para upsert no destructivo."
        )

    _reset_db()
    rng = random.Random(SEMILLA)
    db = SessionLocal()
    try:
        db.add_all(
            [
                Usuario(
                    email=ADMIN_EMAIL,
                    nombre="Administrador",
                    password_hash=hash_password(ADMIN_PASSWORD),
                    rol=RolUsuario.admin,
                ),
                Usuario(
                    email=USER_EMAIL,
                    nombre="Usuario Demo",
                    password_hash=hash_password(USER_PASSWORD),
                    rol=RolUsuario.usuario,
                ),
            ]
        )

        base_historico = datetime.now(timezone.utc) - timedelta(days=90)
        base_proximo = datetime.now(timezone.utc)

        total_hist = 0
        total_prox = 0
        for spec in COMPETICIONES:
            h, p = _crear_competicion(db, spec, rng, base_historico, base_proximo)
            total_hist += h
            total_prox += p

        db.commit()
        print("Dataset de copas de America creado correctamente.")
        print(f"  Competiciones: {len(COMPETICIONES)}")
        for spec in COMPETICIONES:
            print(f"    - {spec.nombre} ({spec.region})")
        print(f"  Partidos historicos: {total_hist}")
        print(f"  Partidos proximos:   {total_prox}")
        print(f"  Admin:   {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print(f"  Usuario: {USER_EMAIL} / {USER_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

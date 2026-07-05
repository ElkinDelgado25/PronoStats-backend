"""Datos de ejemplo para desarrollo y demostracion.

Uso:
    python -m app.seed

Crea un usuario admin, un usuario normal, una liga con equipos y varios
partidos (con resultados historicos) para que el motor de pronostico y el
panel de metricas tengan datos con que trabajar.
"""

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


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed() -> None:
    _reset_db()
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

        liga = Liga(nombre="Liga Demo", pais="Internacional", temporada="2025/26")
        db.add(liga)
        db.flush()

        nombres = ["Tigres", "Aguilas", "Leones", "Toros"]
        equipos = [Equipo(nombre=n, liga_id=liga.id) for n in nombres]
        db.add_all(equipos)
        db.flush()

        base = datetime.now(timezone.utc) - timedelta(days=40)
        # Partidos historicos con resultados (round-robin simple).
        historicos = [
            (0, 1, 2, 0),
            (2, 3, 1, 1),
            (0, 2, 3, 1),
            (1, 3, 0, 2),
            (0, 3, 2, 2),
            (1, 2, 1, 0),
            (2, 0, 0, 1),
            (3, 1, 1, 3),
        ]
        dia = 0
        for local_idx, visit_idx, gl, gv in historicos:
            partido = Partido(
                liga_id=liga.id,
                local_id=equipos[local_idx].id,
                visitante_id=equipos[visit_idx].id,
                fecha=base + timedelta(days=dia),
                estado=EstadoPartido.finalizado,
            )
            db.add(partido)
            db.flush()
            partido.resultado = Resultado(
                partido_id=partido.id, goles_local=gl, goles_visitante=gv
            )
            # Genera y evalua prediccion (para poblar el panel de metricas).
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
            db.flush()
            evaluar_prediccion(partido)
            dia += 3

        # Partidos futuros (programados) para pronosticar.
        futuros = [(0, 3), (1, 2), (3, 0)]
        for offset, (local_idx, visit_idx) in enumerate(futuros):
            db.add(
                Partido(
                    liga_id=liga.id,
                    local_id=equipos[local_idx].id,
                    visitante_id=equipos[visit_idx].id,
                    fecha=datetime.now(timezone.utc) + timedelta(days=offset + 1),
                    estado=EstadoPartido.programado,
                )
            )

        db.commit()
        print("Datos de ejemplo creados correctamente.")
        print(f"  Admin:   {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print(f"  Usuario: {USER_EMAIL} / {USER_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

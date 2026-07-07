"""Generador de los datasets CSV de PronoStats.

Uso:
    python -m app.generate_dataset

Crea (o regenera) dos archivos en `PronoStats-backend/data/dataset_futbol/`:
  - equipos.csv : equipos de la liga principal de varios paises de America.
  - goles.csv   : partidos historicos (finalizados, con goles) y proximos
                  (programados, sin goles).

Los resultados historicos se simulan de forma DETERMINISTA (semilla fija) con
un modelo de goles de Poisson basado en la "fuerza" de cada equipo. Este script
NO toca la base de datos: solo escribe archivos CSV que la aplicacion lee en
cada arranque.
"""

import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEMILLA = 2026
HOME_ADVANTAGE_GOLES = 0.35
DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
DATASET_DIR = DATA_ROOT / "dataset_futbol"

# Liga principal por pais: nombre_liga -> (pais, [(equipo, fuerza), ...])
LIGAS: dict[str, tuple[str, list[tuple[str, float]]]] = {
    "Liga Profesional": (
        "Argentina",
        [
            ("River Plate", 0.84),
            ("Boca Juniors", 0.80),
            ("Racing Club", 0.74),
            ("Independiente", 0.66),
            ("San Lorenzo", 0.62),
            ("Estudiantes", 0.68),
            ("Velez Sarsfield", 0.70),
            ("Talleres", 0.64),
        ],
    ),
    "Brasileirao Serie A": (
        "Brasil",
        [
            ("Flamengo", 0.86),
            ("Palmeiras", 0.85),
            ("Corinthians", 0.72),
            ("Sao Paulo", 0.74),
            ("Fluminense", 0.70),
            ("Gremio", 0.68),
            ("Internacional", 0.69),
            ("Atletico Mineiro", 0.76),
        ],
    ),
    "Liga MX": (
        "Mexico",
        [
            ("America", 0.82),
            ("Guadalajara", 0.70),
            ("Cruz Azul", 0.76),
            ("Monterrey", 0.78),
            ("Tigres UANL", 0.79),
            ("Pumas UNAM", 0.66),
            ("Toluca", 0.72),
            ("Leon", 0.68),
        ],
    ),
    "LigaPro Serie A": (
        "Ecuador",
        [
            ("LDU Quito", 0.78),
            ("Barcelona SC", 0.74),
            ("Emelec", 0.66),
            ("Independiente del Valle", 0.80),
            ("Aucas", 0.62),
            ("Deportivo Cuenca", 0.58),
            ("Delfin", 0.60),
            ("Universidad Catolica", 0.61),
        ],
    ),
    "Categoria Primera A": (
        "Colombia",
        [
            ("Atletico Nacional", 0.80),
            ("Millonarios", 0.74),
            ("America de Cali", 0.72),
            ("Deportivo Cali", 0.66),
            ("Junior", 0.73),
            ("Santa Fe", 0.68),
            ("Deportes Tolima", 0.70),
            ("Once Caldas", 0.62),
        ],
    ),
    "MLS": (
        "Estados Unidos",
        [
            ("LA Galaxy", 0.72),
            ("LAFC", 0.78),
            ("Inter Miami", 0.80),
            ("Seattle Sounders", 0.74),
            ("Atlanta United", 0.70),
            ("Portland Timbers", 0.66),
            ("NYCFC", 0.71),
            ("Austin FC", 0.64),
        ],
    ),
}

# Partidos proximos destacados por liga (indices de equipo dentro de la liga).
PROXIMOS_POR_LIGA: dict[str, list[tuple[int, int]]] = {
    "Liga Profesional": [(0, 1), (2, 6)],
    "Brasileirao Serie A": [(0, 1), (7, 2)],
    "Liga MX": [(0, 2), (4, 3)],
    "LigaPro Serie A": [(3, 0), (1, 2)],
    "Categoria Primera A": [(0, 1), (4, 2)],
    "MLS": [(2, 1), (3, 0)],
}


def _poisson(rng: random.Random, lam: float) -> int:
    limite = math.exp(-lam)
    k = 0
    prod = 1.0
    while True:
        k += 1
        prod *= rng.random()
        if prod <= limite:
            return k - 1


def _simular_marcador(rng: random.Random, fuerza_local: float, fuerza_visitante: float) -> tuple[int, int]:
    lam_local = 0.75 + fuerza_local * 2.0 + HOME_ADVANTAGE_GOLES
    lam_visitante = 0.75 + fuerza_visitante * 2.0
    return min(_poisson(rng, lam_local), 6), min(_poisson(rng, lam_visitante), 6)


def generar() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEMILLA)

    equipos_rows: list[dict] = []
    # equipo_id global e indice local por liga
    ids_por_liga: dict[str, list[int]] = {}
    fuerza_por_id: dict[int, float] = {}
    equipo_id = 1
    for liga, (pais, equipos) in LIGAS.items():
        ids_por_liga[liga] = []
        for nombre, fuerza in equipos:
            equipos_rows.append(
                {
                    "equipo_id": equipo_id,
                    "nombre": nombre,
                    "liga": liga,
                    "pais": pais,
                    "fuerza": f"{fuerza:.2f}",
                }
            )
            ids_por_liga[liga].append(equipo_id)
            fuerza_por_id[equipo_id] = fuerza
            equipo_id += 1

    with (DATASET_DIR / "equipos.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["equipo_id", "nombre", "liga", "pais", "fuerza"])
        writer.writeheader()
        writer.writerows(equipos_rows)

    # ---- goles.csv ----
    partidos_rows: list[dict] = []
    partido_id = 1
    base_hist = datetime.now(timezone.utc) - timedelta(days=150)

    for liga, ids in ids_por_liga.items():
        n = len(ids)
        # Doble round-robin (ida y vuelta) -> historial finalizado.
        fixtures = [(i, j) for i in range(n) for j in range(n) if i != j]
        rng.shuffle(fixtures)
        dia = 0
        for local_idx, visit_idx in fixtures:
            gl, gv = _simular_marcador(
                rng, fuerza_por_id[ids[local_idx]], fuerza_por_id[ids[visit_idx]]
            )
            fecha = base_hist + timedelta(days=dia, hours=rng.randint(12, 21))
            partidos_rows.append(
                {
                    "partido_id": partido_id,
                    "liga": liga,
                    "equipo_local_id": ids[local_idx],
                    "equipo_visitante_id": ids[visit_idx],
                    "fecha": fecha.isoformat(),
                    "estado": "finalizado",
                    "goles_local": gl,
                    "goles_visitante": gv,
                }
            )
            partido_id += 1
            dia += 1

    # Partidos proximos (programados, sin goles).
    base_prox = datetime.now(timezone.utc)
    for liga, pares in PROXIMOS_POR_LIGA.items():
        ids = ids_por_liga[liga]
        for offset, (local_idx, visit_idx) in enumerate(pares):
            fecha = base_prox + timedelta(days=offset + 1, hours=19)
            partidos_rows.append(
                {
                    "partido_id": partido_id,
                    "liga": liga,
                    "equipo_local_id": ids[local_idx],
                    "equipo_visitante_id": ids[visit_idx],
                    "fecha": fecha.isoformat(),
                    "estado": "programado",
                    "goles_local": "",
                    "goles_visitante": "",
                }
            )
            partido_id += 1

    with (DATASET_DIR / "goles.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "partido_id",
                "liga",
                "equipo_local_id",
                "equipo_visitante_id",
                "fecha",
                "estado",
                "goles_local",
                "goles_visitante",
            ],
        )
        writer.writeheader()
        writer.writerows(partidos_rows)

    finalizados = sum(1 for r in partidos_rows if r["estado"] == "finalizado")
    programados = len(partidos_rows) - finalizados
    print("Datasets generados en", DATASET_DIR)
    print(f"  equipos.csv: {len(equipos_rows)} equipos en {len(LIGAS)} ligas")
    print(f"  goles.csv:   {len(partidos_rows)} partidos ({finalizados} finalizados, {programados} programados)")


if __name__ == "__main__":
    generar()

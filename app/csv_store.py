"""Proveedor de datos basado en CSV, cargado en memoria.

Este modulo es INDEPENDIENTE de la base de datos (SQLAlchemy). Lee los archivos
`data/dataset_futbol/equipos.csv` y `data/dataset_futbol/goles.csv` en cada arranque del backend (invocado
desde el lifespan de FastAPI) y expone los datos ya listos para la API:
ligas, equipos, partidos, pronosticos 1X2 y metricas del modelo.

El pronostico y la evaluacion (acierto/fallo) se calculan al cargar, usando el
mismo motor `prediction_engine.compute_prediction`, garantizando que la
prediccion de cada partido finalizado use SOLO el historial previo a su fecha
(sin fuga de informacion).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.services.agents.base import AgentContext, AgentResult
from app.services.agents.registry import run_all_agents
from app.services.team_stats import TeamForm

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
DATASET_DIR = DATA_ROOT / "dataset_futbol"
EQUIPOS_CSV = DATASET_DIR / "equipos.csv"
GOLES_CSV = DATASET_DIR / "goles.csv"
TEMPORADA = "2026"


PAIS_A_CODIGO_BANDERA: dict[str, str] = {
    "Argentina": "ar",
    "Brasil": "br",
    "Colombia": "co",
    "Mexico": "mx",
    "Ecuador": "ec",
    "Estados Unidos": "us",
}


def _escudo_liga(pais: str) -> str | None:
    code = PAIS_A_CODIGO_BANDERA.get(pais)
    if not code:
        return None
    return f"https://flagcdn.com/w40/{code}.png"


@dataclass
class LigaDTO:
    id: int
    nombre: str
    pais: str
    temporada: str
    escudo_url: str | None = None


@dataclass
class EquipoDTO:
    id: int
    nombre: str
    liga_id: int
    escudo_url: str | None = None


@dataclass
class ResultadoDTO:
    goles_local: int
    goles_visitante: int

    @property
    def ganador(self) -> str:
        if self.goles_local > self.goles_visitante:
            return "local"
        if self.goles_local < self.goles_visitante:
            return "visitante"
        return "empate"


@dataclass
class PartidoDTO:
    id: int
    liga_id: int
    fecha: datetime
    estado: str
    local: EquipoDTO
    visitante: EquipoDTO
    resultado: ResultadoDTO | None = None


@dataclass
class FactorDTO:
    equipo: str
    forma_reciente: float
    promedio_goles_favor: float
    promedio_goles_contra: float


@dataclass
class PrediccionDTO:
    partido_id: int
    prob_local: float
    prob_empate: float
    prob_visitante: float
    pronostico: str
    confianza: float
    modelo_version: str
    factores: list[FactorDTO] = field(default_factory=list)


@dataclass
class PrediccionCategoriaDTO:
    categoria: str
    pronostico: str
    confianza: float
    probabilidades: dict[str, float]
    modelo_version: str
    factores: list[dict] = field(default_factory=list)


class CsvStore:
    def __init__(self) -> None:
        self.ligas: list[LigaDTO] = []
        self._liga_por_nombre: dict[str, LigaDTO] = {}
        self.equipos: dict[int, EquipoDTO] = {}
        self.partidos: dict[int, PartidoDTO] = {}
        self._predicciones: dict[int, PrediccionDTO] = {}
        self._predicciones_categorias: dict[int, dict[str, PrediccionCategoriaDTO]] = {}
        self._aciertos: dict[int, bool] = {}
        self._finalizados_ordenados: list[PartidoDTO] = []

    # ------------------------------------------------------------------ carga
    def load(self) -> None:
        """(Re)lee los CSV desde disco y recalcula pronosticos y metricas."""
        self.__init__()
        self._cargar_equipos()
        self._cargar_partidos()
        self._precalcular()

    def _cargar_equipos(self) -> None:
        with EQUIPOS_CSV.open(newline="", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                nombre_liga = fila["liga"].strip()
                liga = self._liga_por_nombre.get(nombre_liga)
                if liga is None:
                    liga = LigaDTO(
                        id=len(self.ligas) + 1,
                        nombre=nombre_liga,
                        pais=fila["pais"].strip(),
                        temporada=TEMPORADA,
                        escudo_url=_escudo_liga(fila["pais"].strip()),
                    )
                    self.ligas.append(liga)
                    self._liga_por_nombre[nombre_liga] = liga
                eid = int(fila["equipo_id"])
                self.equipos[eid] = EquipoDTO(id=eid, nombre=fila["nombre"].strip(), liga_id=liga.id)

    def _cargar_partidos(self) -> None:
        with GOLES_CSV.open(newline="", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                liga = self._liga_por_nombre.get(fila["liga"].strip())
                if liga is None:
                    continue
                local = self.equipos.get(int(fila["equipo_local_id"]))
                visitante = self.equipos.get(int(fila["equipo_visitante_id"]))
                if local is None or visitante is None:
                    continue
                estado = fila["estado"].strip()
                resultado = None
                if estado == "finalizado" and fila["goles_local"] != "" and fila["goles_visitante"] != "":
                    resultado = ResultadoDTO(
                        goles_local=int(fila["goles_local"]),
                        goles_visitante=int(fila["goles_visitante"]),
                    )
                pid = int(fila["partido_id"])
                self.partidos[pid] = PartidoDTO(
                    id=pid,
                    liga_id=liga.id,
                    fecha=datetime.fromisoformat(fila["fecha"]),
                    estado=estado,
                    local=local,
                    visitante=visitante,
                    resultado=resultado,
                )

    # --------------------------------------------------------------- forma
    def _finalizados(self) -> list[PartidoDTO]:
        return [p for p in self.partidos.values() if p.estado == "finalizado" and p.resultado]

    def _forma(self, equipo_id: int, antes_de: datetime | None, limite: int) -> TeamForm:
        candidatos = [
            p
            for p in self._finalizados()
            if (p.local.id == equipo_id or p.visitante.id == equipo_id)
            and (antes_de is None or p.fecha < antes_de)
        ]
        candidatos.sort(key=lambda p: p.fecha, reverse=True)
        candidatos = candidatos[:limite]

        v = e = d = gf = gc = 0
        for p in candidatos:
            assert p.resultado is not None
            es_local = p.local.id == equipo_id
            f = p.resultado.goles_local if es_local else p.resultado.goles_visitante
            c = p.resultado.goles_visitante if es_local else p.resultado.goles_local
            gf += f
            gc += c
            if f > c:
                v += 1
            elif f == c:
                e += 1
            else:
                d += 1
        return TeamForm(
            equipo_id=equipo_id,
            partidos_jugados=v + e + d,
            victorias=v,
            empates=e,
            derrotas=d,
            goles_favor=gf,
            goles_contra=gc,
        )

    def _build_context(self, partido: PartidoDTO) -> AgentContext:
        n = settings.prediction_recent_form_matches
        antes = partido.fecha if partido.estado == "finalizado" else None
        forma_local = self._forma(partido.local.id, antes, n)
        forma_visitante = self._forma(partido.visitante.id, antes, n)
        return AgentContext(
            partido_id=partido.id,
            local_nombre=partido.local.nombre,
            visitante_nombre=partido.visitante.nombre,
            forma_local=forma_local,
            forma_visitante=forma_visitante,
        )

    @staticmethod
    def _categoria_to_dto(result: AgentResult) -> PrediccionCategoriaDTO:
        return PrediccionCategoriaDTO(
            categoria=result.categoria,
            pronostico=result.pronostico,
            confianza=result.confianza,
            probabilidades=result.probabilidades,
            modelo_version=result.modelo_version,
            factores=result.factores,
        )

    @staticmethod
    def _match_result_to_legacy(partido_id: int, cat: PrediccionCategoriaDTO) -> PrediccionDTO:
        factores = [
            FactorDTO(
                equipo=f["equipo"],
                forma_reciente=f["forma_reciente"],
                promedio_goles_favor=f["promedio_goles_favor"],
                promedio_goles_contra=f["promedio_goles_contra"],
            )
            for f in cat.factores
            if "equipo" in f
        ]
        return PrediccionDTO(
            partido_id=partido_id,
            prob_local=cat.probabilidades["local"],
            prob_empate=cat.probabilidades["empate"],
            prob_visitante=cat.probabilidades["visitante"],
            pronostico=cat.pronostico,
            confianza=cat.confianza,
            modelo_version=cat.modelo_version,
            factores=factores,
        )

    def _predecir_todas(self, partido: PartidoDTO) -> dict[str, PrediccionCategoriaDTO]:
        ctx = self._build_context(partido)
        return {
            categoria: self._categoria_to_dto(result)
            for categoria, result in run_all_agents(ctx).items()
        }

    def _precalcular(self) -> None:
        self._finalizados_ordenados = sorted(self._finalizados(), key=lambda p: p.fecha)
        for partido in self.partidos.values():
            categorias = self._predecir_todas(partido)
            self._predicciones_categorias[partido.id] = categorias
            self._predicciones[partido.id] = self._match_result_to_legacy(
                partido.id, categorias["match_result"]
            )
            pred = self._predicciones[partido.id]
            if partido.estado == "finalizado" and partido.resultado is not None:
                self._aciertos[partido.id] = pred.pronostico == partido.resultado.ganador

    # ------------------------------------------------------------- consultas
    def get_ligas(self) -> list[LigaDTO]:
        return sorted(self.ligas, key=lambda l: l.nombre)

    def get_paises(self) -> list[str]:
        """Paises con al menos una liga disponible en el catalogo publico."""
        return sorted({liga.pais for liga in self.ligas})

    def get_liga(self, liga_id: int) -> LigaDTO | None:
        for liga in self.ligas:
            if liga.id == liga_id:
                return liga
        return None

    def get_equipos(self, liga_id: int | None = None) -> list[EquipoDTO]:
        equipos = self.equipos.values()
        if liga_id is not None:
            equipos = [e for e in equipos if e.liga_id == liga_id]
        return sorted(equipos, key=lambda e: e.nombre)

    def get_equipo(self, equipo_id: int) -> EquipoDTO | None:
        return self.equipos.get(equipo_id)

    def get_partidos(
        self,
        liga_id: int | None = None,
        fecha=None,
        estado: str | None = None,
    ) -> list[PartidoDTO]:
        partidos = list(self.partidos.values())
        if liga_id is not None:
            partidos = [p for p in partidos if p.liga_id == liga_id]
        if estado is not None:
            partidos = [p for p in partidos if p.estado == estado]
        if fecha is not None:
            partidos = [p for p in partidos if p.fecha.date() == fecha]
        return sorted(partidos, key=lambda p: p.fecha)

    def get_partido(self, partido_id: int) -> PartidoDTO | None:
        return self.partidos.get(partido_id)

    def get_prediccion(self, partido_id: int) -> PrediccionDTO | None:
        return self._predicciones.get(partido_id)

    def get_predicciones_publicas(
        self,
        liga_id: int | None = None,
        fecha=None,
        estado: str | None = None,
    ) -> list[PrediccionDTO]:
        """Lista los pronosticos 1X2 asociados a los partidos filtrados."""
        return [
            self._predicciones[partido.id]
            for partido in self.get_partidos(liga_id=liga_id, fecha=fecha, estado=estado)
            if partido.id in self._predicciones
        ]

    def get_predicciones(
        self, partido_id: int, categoria: str | None = None
    ) -> list[PrediccionCategoriaDTO] | None:
        categorias = self._predicciones_categorias.get(partido_id)
        if categorias is None:
            return None
        if categoria is not None:
            cat = categorias.get(categoria)
            return [cat] if cat is not None else []
        return list(categorias.values())

    def get_team_stats(self, equipo_id: int) -> dict | None:
        equipo = self.equipos.get(equipo_id)
        if equipo is None:
            return None
        forma = self._forma(equipo_id, None, limite=10_000)
        return {
            "equipo_id": equipo.id,
            "nombre": equipo.nombre,
            "partidos_jugados": forma.partidos_jugados,
            "victorias": forma.victorias,
            "empates": forma.empates,
            "derrotas": forma.derrotas,
            "goles_favor": forma.goles_favor,
            "goles_contra": forma.goles_contra,
            "promedio_goles_favor": round(forma.promedio_goles_favor, 2),
            "promedio_goles_contra": round(forma.promedio_goles_contra, 2),
            "forma_reciente": round(forma.forma_reciente, 4),
        }

    def get_h2h_by_teams(self, equipo_a_id: int, equipo_b_id: int) -> dict | None:
        equipo_a = self.equipos.get(equipo_a_id)
        equipo_b = self.equipos.get(equipo_b_id)
        if equipo_a is None or equipo_b is None:
            return None

        historial = [
            p
            for p in self._finalizados()
            if {p.local.id, p.visitante.id} == {equipo_a_id, equipo_b_id}
        ]
        historial.sort(key=lambda p: p.fecha, reverse=True)

        victorias_a = empates = victorias_b = 0
        for p in historial:
            assert p.resultado is not None
            ganador = p.resultado.ganador
            if ganador == "empate":
                empates += 1
            elif (ganador == "local" and p.local.id == equipo_a_id) or (
                ganador == "visitante" and p.visitante.id == equipo_a_id
            ):
                victorias_a += 1
            else:
                victorias_b += 1

        return {
            "total_partidos": len(historial),
            "victorias_equipo_a": victorias_a,
            "empates": empates,
            "victorias_equipo_b": victorias_b,
            "historial": historial[:10],
        }

    @staticmethod
    def _comparar_valor(
        valor_a: float,
        valor_b: float,
        nombre_a: str,
        nombre_b: str,
        menor_es_mejor: bool = False,
    ) -> str:
        if valor_a == valor_b:
            return "Empate"
        if menor_es_mejor:
            return nombre_a if valor_a < valor_b else nombre_b
        return nombre_a if valor_a > valor_b else nombre_b

    def compare_teams(self, equipo_a_id: int, equipo_b_id: int) -> dict | None:
        if equipo_a_id == equipo_b_id:
            return None

        stats_a = self.get_team_stats(equipo_a_id)
        stats_b = self.get_team_stats(equipo_b_id)
        h2h = self.get_h2h_by_teams(equipo_a_id, equipo_b_id)
        if stats_a is None or stats_b is None or h2h is None:
            return None

        nombre_a = stats_a["nombre"]
        nombre_b = stats_b["nombre"]
        puntos_a = (
            stats_a["forma_reciente"]
            + stats_a["promedio_goles_favor"] / 4
            - stats_a["promedio_goles_contra"] / 4
        )
        puntos_b = (
            stats_b["forma_reciente"]
            + stats_b["promedio_goles_favor"] / 4
            - stats_b["promedio_goles_contra"] / 4
        )

        return {
            "equipo_a": stats_a,
            "equipo_b": stats_b,
            "enfrentamientos_directos": h2h,
            "resumen": {
                "mejor_forma": self._comparar_valor(
                    stats_a["forma_reciente"], stats_b["forma_reciente"], nombre_a, nombre_b
                ),
                "mejor_ataque": self._comparar_valor(
                    stats_a["promedio_goles_favor"],
                    stats_b["promedio_goles_favor"],
                    nombre_a,
                    nombre_b,
                ),
                "mejor_defensa": self._comparar_valor(
                    stats_a["promedio_goles_contra"],
                    stats_b["promedio_goles_contra"],
                    nombre_a,
                    nombre_b,
                    menor_es_mejor=True,
                ),
                "ventaja_general": self._comparar_valor(
                    round(puntos_a, 4), round(puntos_b, 4), nombre_a, nombre_b
                ),
            },
        }

    def get_h2h(self, partido_id: int) -> dict | None:
        partido = self.partidos.get(partido_id)
        if partido is None:
            return None
        a, b = partido.local.id, partido.visitante.id
        historial = [
            p
            for p in self._finalizados()
            if {p.local.id, p.visitante.id} == {a, b}
        ]
        historial.sort(key=lambda p: p.fecha, reverse=True)

        vic_local = empates = vic_visitante = 0
        for p in historial:
            assert p.resultado is not None
            ganador = p.resultado.ganador
            if ganador == "empate":
                empates += 1
            elif (ganador == "local" and p.local.id == a) or (
                ganador == "visitante" and p.visitante.id == a
            ):
                vic_local += 1
            else:
                vic_visitante += 1
        return {
            "total_partidos": len(historial),
            "victorias_local": vic_local,
            "empates": empates,
            "victorias_visitante": vic_visitante,
            "historial": historial,
        }

    def get_model_performance(self) -> dict:
        finalizados = self._finalizados_ordenados
        total = len(finalizados)
        aciertos = sum(1 for p in finalizados if self._aciertos.get(p.id))
        fallos = total - aciertos
        precision = round(aciertos / total, 4) if total else 0.0

        # Tendencia acumulada agregada por dia (para un grafico legible).
        tendencia: list[dict] = []
        acc_ac = acc_tot = 0
        por_dia: dict[str, dict] = {}
        for p in finalizados:
            acc_tot += 1
            if self._aciertos.get(p.id):
                acc_ac += 1
            dia = p.fecha.date().isoformat()
            por_dia[dia] = {
                "fecha": dia,
                "aciertos": acc_ac,
                "fallos": acc_tot - acc_ac,
                "precision_acumulada": round(acc_ac / acc_tot, 4),
            }
        tendencia = list(por_dia.values())

        modelo_version = (
            self._predicciones[finalizados[-1].id].modelo_version if finalizados else ""
        )
        return {
            "total_evaluadas": total,
            "aciertos": aciertos,
            "fallos": fallos,
            "precision": precision,
            "modelo_version": modelo_version,
            "tendencia": tendencia,
        }


# Instancia global. Se (re)carga en el lifespan de FastAPI en cada arranque.
store = CsvStore()

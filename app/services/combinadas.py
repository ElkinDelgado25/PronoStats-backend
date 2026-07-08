from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.csv_store import store
from app.schemas.combinada import (
    CombinadaCalcularIn,
    CombinadaCalcularOut,
    MercadoOut,
    SeleccionCombinadaIn,
    SeleccionCombinadaOut,
    SubCombinadaOut,
    TipoCombinada,
)

CATEGORIA_LABELS: dict[str, str] = {
    "match_result": "1X2",
    "total_goals": "Total goles",
    "btts": "Ambos marcan",
    "goal_timing": "Timing de goles",
    "first_scorer": "Primer gol",
    "double_chance": "Doble oportunidad",
}

SELECCION_LABELS: dict[str, dict[str, str]] = {
    "match_result": {
        "local": "Local",
        "empate": "Empate",
        "visitante": "Visitante",
    },
    "total_goals": {
        "over_0_5": "Mas de 0.5",
        "under_0_5": "Menos de 0.5",
        "over_1_5": "Mas de 1.5",
        "under_1_5": "Menos de 1.5",
        "over_2_5": "Mas de 2.5",
        "under_2_5": "Menos de 2.5",
        "over_3_5": "Mas de 3.5",
        "under_3_5": "Menos de 3.5",
    },
    "btts": {"si": "Si", "no": "No"},
    "goal_timing": {
        "0-15": "0-15 min",
        "16-30": "16-30 min",
        "31-45": "31-45 min",
        "46-60": "46-60 min",
        "61-75": "61-75 min",
        "76-90": "76-90 min",
    },
    "first_scorer": {
        "local": "Local",
        "visitante": "Visitante",
        "sin_goles": "Sin goles",
    },
    "double_chance": {
        "local_o_empate": "Local o empate",
        "visitante_o_empate": "Visitante o empate",
        "local_o_visitante": "Local o visitante",
    },
}

MERCADOS_CATALOGO: list[MercadoOut] = [
    MercadoOut(
        categoria=cat,
        label=CATEGORIA_LABELS[cat],
        selecciones=[{"key": k, "label": v} for k, v in opts.items()],
    )
    for cat, opts in SELECCION_LABELS.items()
]


@dataclass
class LegResuelto:
    partido_id: int
    partido: str
    fecha: str
    categoria: str
    seleccion: str
    probabilidad: float


def normalizar_seleccion(categoria: str, seleccion: str) -> str:
    key = seleccion.strip().lower().replace(" ", "_").replace(".", "_")
    aliases = {
        "over_2.5": "over_2_5",
        "under_2.5": "under_2_5",
        "over_1.5": "over_1_5",
        "under_1.5": "under_1_5",
        "over_0.5": "over_0_5",
        "under_0.5": "under_0_5",
        "over_3.5": "over_3_5",
        "under_3.5": "under_3_5",
        "1": "local",
        "x": "empate",
        "2": "visitante",
        "yes": "si",
        "no": "no",
    }
    key = aliases.get(key, key)
    if categoria == "double_chance" and key in {"local_o_empate", "1x", "1_x"}:
        return "local_o_empate"
    if categoria == "double_chance" and key in {"visitante_o_empate", "x2", "x_2"}:
        return "visitante_o_empate"
    if categoria == "double_chance" and key in {"local_o_visitante", "12", "1_2"}:
        return "local_o_visitante"
    return key


def _prob_a_cuota(prob: float) -> float:
    p = min(max(prob, 0.01), 0.99)
    return round(1 / p, 2)


def _double_chance_probs(probs_1x2: dict[str, float]) -> dict[str, float]:
    local = probs_1x2.get("local", 0.0)
    empate = probs_1x2.get("empate", 0.0)
    visitante = probs_1x2.get("visitante", 0.0)
    return {
        "local_o_empate": round(local + empate, 4),
        "visitante_o_empate": round(visitante + empate, 4),
        "local_o_visitante": round(local + visitante, 4),
    }


def _resolver_probabilidades(partido_id: int, categoria: str) -> dict[str, float]:
    if categoria == "double_chance":
        preds = store.get_predicciones(partido_id, "match_result")
        if not preds:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No hay pronostico 1X2 para el partido {partido_id}",
            )
        return _double_chance_probs(preds[0].probabilidades)

    preds = store.get_predicciones(partido_id, categoria)
    if not preds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoria '{categoria}' no disponible para el partido {partido_id}",
        )
    return preds[0].probabilidades


def _resolver_leg(leg: SeleccionCombinadaIn) -> LegResuelto:
    partido = store.get_partido(leg.partido_id)
    if partido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partido {leg.partido_id} no encontrado",
        )

    categoria = leg.categoria.strip().lower()
    if categoria not in SELECCION_LABELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Categoria '{categoria}' no valida",
        )

    seleccion = normalizar_seleccion(categoria, leg.seleccion)
    probabilidades = _resolver_probabilidades(leg.partido_id, categoria)

    if seleccion not in probabilidades:
        validas = ", ".join(sorted(probabilidades.keys()))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Seleccion '{leg.seleccion}' no valida para '{categoria}' "
                f"en partido {leg.partido_id}. Opciones: {validas}"
            ),
        )

    return LegResuelto(
        partido_id=leg.partido_id,
        partido=f"{partido.local.nombre} vs {partido.visitante.nombre}",
        fecha=partido.fecha.strftime("%d/%m/%Y"),
        categoria=categoria,
        seleccion=seleccion,
        probabilidad=probabilidades[seleccion],
    )


def _leg_a_out(leg: LegResuelto) -> SeleccionCombinadaOut:
    labels = SELECCION_LABELS.get(leg.categoria, {})
    return SeleccionCombinadaOut(
        partido_id=leg.partido_id,
        partido=leg.partido,
        fecha=leg.fecha,
        categoria=leg.categoria,
        categoria_label=CATEGORIA_LABELS.get(leg.categoria, leg.categoria),
        seleccion=leg.seleccion,
        seleccion_label=labels.get(leg.seleccion, leg.seleccion),
        probabilidad=round(leg.probabilidad, 4),
        cuota=_prob_a_cuota(leg.probabilidad),
    )


def _validar_duplicados(legs: list[LegResuelto]) -> None:
    vistos: set[tuple[int, str]] = set()
    for leg in legs:
        key = (leg.partido_id, leg.categoria)
        if key in vistos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Seleccion duplicada: partido {leg.partido_id} "
                    f"categoria {leg.categoria}"
                ),
            )
        vistos.add(key)


def _advertencias(legs: list[LegResuelto]) -> list[str]:
    msgs: list[str] = []
    partidos = {leg.partido_id for leg in legs}
    if len(partidos) < len(legs):
        msgs.append(
            "Varias selecciones del mismo partido: las probabilidades pueden estar "
            "correlacionadas y la cuota combinada es una aproximacion."
        )
    return msgs


def _calcular_multiple(legs: list[LegResuelto]) -> tuple[float, float]:
    prob = math.prod(leg.probabilidad for leg in legs)
    cuota = _prob_a_cuota(prob)
    return round(prob, 4), cuota


def _combinaciones_sistema(n: int, k: int) -> list[tuple[int, ...]]:
    return list(itertools.combinations(range(n), k))


def calcular_combinada(payload: CombinadaCalcularIn) -> CombinadaCalcularOut:
    legs = [_resolver_leg(s) for s in payload.selecciones]
    _validar_duplicados(legs)
    advertencias = _advertencias(legs)
    selecciones_out = [_leg_a_out(leg) for leg in legs]

    if payload.tipo == TipoCombinada.individual:
        importe = payload.importe
        if importe <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El importe debe ser mayor a 0 para apuestas individuales",
            )
        ganancia = sum(importe * s.cuota for s in selecciones_out)
        return CombinadaCalcularOut(
            tipo=payload.tipo,
            selecciones=selecciones_out,
            num_pronosticos=len(selecciones_out),
            valor_total=round(importe * len(selecciones_out), 2),
            ganancia_potencial=round(ganancia, 2),
            advertencias=advertencias,
        )

    if payload.tipo == TipoCombinada.multiple:
        importe = payload.importe
        if importe <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El importe debe ser mayor a 0 para apuesta multiple",
            )
        prob, cuota = _calcular_multiple(legs)
        return CombinadaCalcularOut(
            tipo=payload.tipo,
            selecciones=selecciones_out,
            cuota_combinada=cuota,
            probabilidad_combinada=prob,
            num_pronosticos=1,
            valor_total=round(importe, 2),
            ganancia_potencial=round(importe * cuota, 2),
            advertencias=advertencias,
        )

    # Sistema
    k = payload.sistema_k
    if k is None:
        k = len(legs) - 1 if len(legs) > 2 else 2
    if k < 2 or k > len(legs):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"sistema_k debe estar entre 2 y {len(legs)}",
        )

    importe_combo = payload.importe_por_combinacion or payload.importe
    if importe_combo <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El importe por combinacion debe ser mayor a 0",
        )

    sub_combinaciones: list[SubCombinadaOut] = []
    for indices in _combinaciones_sistema(len(legs), k):
        sub_legs = [legs[i] for i in indices]
        prob, cuota = _calcular_multiple(sub_legs)
        sub_out = [_leg_a_out(leg) for leg in sub_legs]
        sub_combinaciones.append(
            SubCombinadaOut(
                selecciones=sub_out,
                cuota=cuota,
                probabilidad=prob,
                importe=round(importe_combo, 2),
                ganancia_potencial=round(importe_combo * cuota, 2),
            )
        )

    num_combos = len(sub_combinaciones)
    return CombinadaCalcularOut(
        tipo=payload.tipo,
        selecciones=selecciones_out,
        num_pronosticos=num_combos,
        valor_total=round(importe_combo * num_combos, 2),
        ganancia_potencial=round(
            sum(s.ganancia_potencial for s in sub_combinaciones), 2
        ),
        sub_combinaciones=sub_combinaciones,
        advertencias=advertencias
        + [f"Sistema {k}/{len(legs)}: {num_combos} combinaciones generadas"],
    )


def listar_mercados() -> list[MercadoOut]:
    return MERCADOS_CATALOGO

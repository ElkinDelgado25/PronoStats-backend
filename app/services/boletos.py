from __future__ import annotations

import itertools
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.csv_store import store
from app.models.boleto import Boleto, EstadoBoleto
from app.models.usuario import Usuario
from app.schemas.boleto import BoletoConsultaOut, BoletoCrearIn, BoletoOut
from app.schemas.combinada import CombinadaCalcularIn, TipoCombinada
from app.services.combinadas import (
    _combinaciones_sistema,
    calcular_combinada,
    normalizar_seleccion,
)
from app.services.wallet import acreditar_premio, debitar_apuesta


def _evaluar_seleccion(partido_id: int, categoria: str, seleccion: str) -> bool | None:
    """True=acierto, False=fallo, None=partido sin finalizar o mercado no evaluable."""
    partido = store.get_partido(partido_id)
    if partido is None or partido.estado != "finalizado" or partido.resultado is None:
        return None

    cat = categoria.strip().lower()
    sel = normalizar_seleccion(cat, seleccion)
    gl = partido.resultado.goles_local
    gv = partido.resultado.goles_visitante
    total = gl + gv
    ganador = partido.resultado.ganador

    if cat == "match_result":
        return sel == ganador
    if cat == "double_chance":
        if sel == "local_o_empate":
            return ganador in {"local", "empate"}
        if sel == "visitante_o_empate":
            return ganador in {"visitante", "empate"}
        if sel == "local_o_visitante":
            return ganador in {"local", "visitante"}
    if cat == "btts":
        ambos = gl > 0 and gv > 0
        return ambos if sel == "si" else not ambos
    if cat == "total_goals":
        line = float(sel.replace("over_", "").replace("under_", "").replace("_", "."))
        over = total > line
        return over if sel.startswith("over_") else not over
    if cat == "first_scorer":
        if sel == "sin_goles":
            return total == 0
        if sel == "local":
            return gl > 0 and (gv == 0 or gl <= gv)  # aproximacion sin minuto
        if sel == "visitante":
            return gv > 0 and (gl == 0 or gv < gl)
    if cat == "goal_timing":
        return None  # sin minutos reales no liquidamos este mercado
    return None


def _legs_from_boleto(boleto: Boleto) -> list[dict]:
    return list(boleto.selecciones)


def liquidar_boleto(db: Session, boleto: Boleto) -> Boleto:
    if boleto.estado != EstadoBoleto.pendiente:
        return boleto

    legs = _legs_from_boleto(boleto)
    evaluaciones: list[dict] = []
    pendientes = 0

    for leg in legs:
        ok = _evaluar_seleccion(leg["partido_id"], leg["categoria"], leg["seleccion"])
        evaluaciones.append(
            {
                "partido_id": leg["partido_id"],
                "categoria": leg["categoria"],
                "seleccion": leg["seleccion"],
                "resultado": "pendiente" if ok is None else ("ganado" if ok else "perdido"),
            }
        )
        if ok is None:
            pendientes += 1

    if pendientes > 0:
        boleto.detalle_liquidacion = {"legs": evaluaciones, "pendientes": pendientes}
        db.commit()
        db.refresh(boleto)
        return boleto

    tipo = boleto.tipo
    ganancia = 0.0
    estado = EstadoBoleto.perdido
    sub_wins = 0

    if tipo == TipoCombinada.individual.value:
        aciertos = sum(1 for e in evaluaciones if e["resultado"] == "ganado")
        for leg, ev in zip(legs, evaluaciones):
            if ev["resultado"] == "ganado":
                ganancia += boleto.importe * leg.get("cuota", 1.0)
        if aciertos == len(legs):
            estado = EstadoBoleto.ganado
        elif aciertos > 0:
            estado = EstadoBoleto.parcial
        else:
            estado = EstadoBoleto.perdido

    elif tipo == TipoCombinada.multiple.value:
        if all(e["resultado"] == "ganado" for e in evaluaciones):
            estado = EstadoBoleto.ganado
            ganancia = boleto.ganancia_potencial
        else:
            estado = EstadoBoleto.perdido

    elif tipo == TipoCombinada.sistema.value:
        k = boleto.sistema_k or 2
        importe_combo = boleto.importe
        n = len(legs)
        for indices in _combinaciones_sistema(n, k):
            sub_evals = [evaluaciones[i] for i in indices]
            if all(e["resultado"] == "ganado" for e in sub_evals):
                sub_wins += 1
                cuota = 1.0
                for i in indices:
                    cuota *= legs[i].get("cuota", 1.0)
                ganancia += importe_combo * cuota
        if sub_wins == boleto.num_pronosticos:
            estado = EstadoBoleto.ganado
        elif sub_wins > 0:
            estado = EstadoBoleto.parcial
        else:
            estado = EstadoBoleto.perdido

    boleto.estado = estado
    boleto.ganancia_real = round(ganancia, 2) if ganancia > 0 else 0.0
    boleto.liquidado_en = datetime.now(timezone.utc)
    boleto.detalle_liquidacion = {"legs": evaluaciones, "sub_ganadoras": sub_wins if tipo == "sistema" else None}

    if boleto.ganancia_real and boleto.ganancia_real > 0:
        usuario = db.get(Usuario, boleto.usuario_id)
        if usuario:
            acreditar_premio(db, usuario, boleto.ganancia_real, boleto.uuid)

    db.commit()
    db.refresh(boleto)
    return boleto



def crear_boleto(db: Session, usuario: Usuario, payload: BoletoCrearIn) -> Boleto:
    calc_in = CombinadaCalcularIn(
        tipo=payload.tipo,
        selecciones=payload.selecciones,
        importe=payload.importe,
        importe_por_combinacion=payload.importe_por_combinacion or payload.importe,
        sistema_k=payload.sistema_k,
    )
    resultado = calcular_combinada(calc_in)

    ticket_uuid = str(uuid.uuid4())
    debitar_apuesta(db, usuario, resultado.valor_total, ticket_uuid)

    selecciones_snapshot = [s.model_dump() for s in resultado.selecciones]
    sub_combos = [s.model_dump() for s in resultado.sub_combinaciones] or None

    boleto = Boleto(
        uuid=ticket_uuid,
        usuario_id=usuario.id,
        tipo=resultado.tipo.value,
        estado=EstadoBoleto.pendiente,
        importe=payload.importe,
        valor_total=resultado.valor_total,
        cuota_combinada=resultado.cuota_combinada,
        ganancia_potencial=resultado.ganancia_potencial,
        sistema_k=payload.sistema_k,
        num_pronosticos=resultado.num_pronosticos,
        selecciones=selecciones_snapshot,
        sub_combinaciones=sub_combos,
        advertencias=resultado.advertencias,
    )
    db.add(boleto)
    db.commit()
    db.refresh(boleto)
    return boleto


def consultar_boleto(db: Session, ticket_uuid: str) -> Boleto:
    boleto = db.execute(select(Boleto).where(Boleto.uuid == ticket_uuid)).scalar_one_or_none()
    if boleto is None:
        raise HTTPException(status_code=404, detail="Boleto no encontrado")
    if boleto.estado == EstadoBoleto.pendiente:
        liquidar_boleto(db, boleto)
    return boleto


def listar_boletos_usuario(db: Session, usuario_id: int) -> list[Boleto]:
    stmt = select(Boleto).where(Boleto.usuario_id == usuario_id).order_by(Boleto.creado_en.desc())
    return list(db.execute(stmt).scalars().all())


def liquidar_pendientes(db: Session) -> int:
    boletos = list(
        db.execute(select(Boleto).where(Boleto.estado == EstadoBoleto.pendiente)).scalars().all()
    )
    for b in boletos:
        liquidar_boleto(db, b)
    return len(boletos)


def boleto_a_out(boleto: Boleto) -> BoletoOut:
    return BoletoOut.model_validate(boleto)


def boleto_a_consulta(boleto: Boleto) -> BoletoConsultaOut:
    return BoletoConsultaOut.model_validate(boleto)

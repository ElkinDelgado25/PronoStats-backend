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
from app.services.wallet import acreditar_premio, debitar_apuesta, obtener_o_crear_cartera


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
    if cat in {"first_scorer", "goal_timing"}:
        # Sin datos de minuto no se puede liquidar de forma fiable.
        return None
    return None


def _legs_from_boleto(boleto: Boleto) -> list[dict]:
    return list(boleto.selecciones)


def liquidar_boleto(db: Session, boleto: Boleto) -> Boleto:
    # Bloquea la fila para evitar liquidaciones concurrentes / doble premio.
    locked = db.execute(
        select(Boleto).where(Boleto.id == boleto.id).with_for_update()
    ).scalar_one_or_none()
    if locked is None:
        return boleto
    boleto = locked
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
    boleto.detalle_liquidacion = {
        "legs": evaluaciones,
        "sub_ganadoras": sub_wins if tipo == "sistema" else None,
    }

    # Solo acredita premio si el boleto fue pagado al crearlo (o via /pagar).
    if boleto.pagado and boleto.ganancia_real and boleto.ganancia_real > 0 and boleto.usuario_id:
        usuario = db.get(Usuario, boleto.usuario_id)
        if usuario:
            acreditar_premio(
                db, usuario, boleto.ganancia_real, boleto.uuid, commit=False
            )

    db.commit()
    db.refresh(boleto)
    return boleto


def crear_boleto(
    db: Session, usuario: Usuario | None, payload: BoletoCrearIn
) -> tuple[Boleto, str]:
    """Crea el boleto.

    - Sin sesion: codigo con estado pendiente, no pagado.
    - Con sesion y saldo: debita, pagado=True, estado pendiente (en juego).
    - Con sesion sin saldo: solo codigo, pendiente y no pagado.
    """
    calc_in = CombinadaCalcularIn(
        tipo=payload.tipo,
        selecciones=payload.selecciones,
        importe=payload.importe,
        importe_por_combinacion=payload.importe_por_combinacion or payload.importe,
        sistema_k=payload.sistema_k,
    )
    resultado = calcular_combinada(calc_in)

    ticket_uuid = str(uuid.uuid4())
    codigo = f"PRN-{ticket_uuid.replace('-', '')[:8].upper()}"
    pagado = False

    if usuario is None:
        mensaje = (
            f"Codigo {codigo} generado con estado pendiente. "
            "Inicia sesion para pagarlo y participar por el premio."
        )
    else:
        cartera = obtener_o_crear_cartera(db, usuario, for_update=True, commit=False)
        if cartera.saldo >= resultado.valor_total:
            debitar_apuesta(
                db, usuario, resultado.valor_total, ticket_uuid, commit=False
            )
            pagado = True
            mensaje = f"Pronostico pagado. Codigo {codigo}."
        else:
            mensaje = (
                f"Sin fondos suficientes: codigo {codigo} en estado pendiente. "
                "Recarga tu cartera y pagalo en Historial."
            )

    selecciones_snapshot = [s.model_dump() for s in resultado.selecciones]
    sub_combos = [s.model_dump() for s in resultado.sub_combinaciones] or None

    boleto = Boleto(
        uuid=ticket_uuid,
        usuario_id=usuario.id if usuario else None,
        tipo=resultado.tipo.value,
        estado=EstadoBoleto.pendiente,
        pagado=pagado,
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
    return boleto, mensaje


def reclamar_boletos(db: Session, usuario: Usuario, uuids: list[str]) -> list[Boleto]:
    """Asocia al usuario boletos guest (sin dueño) por UUID."""
    reclamados: list[Boleto] = []
    for ref in uuids:
        boleto = _buscar_boleto(db, ref)
        if boleto is None:
            continue
        if boleto.usuario_id is None:
            boleto.usuario_id = usuario.id
            reclamados.append(boleto)
        elif boleto.usuario_id != usuario.id:
            continue
        else:
            reclamados.append(boleto)
    if reclamados:
        db.commit()
        for b in reclamados:
            db.refresh(b)
    return reclamados


def pagar_boleto(db: Session, usuario: Usuario, referencia: str) -> Boleto:
    """Debita y marca como pagado. Si es guest, lo reclama al usuario."""
    boleto = _buscar_boleto(db, referencia)
    if boleto is None:
        raise HTTPException(status_code=404, detail="Pronostico no encontrado")
    boleto = db.execute(
        select(Boleto).where(Boleto.id == boleto.id).with_for_update()
    ).scalar_one()
    if boleto.usuario_id is None:
        boleto.usuario_id = usuario.id
    elif boleto.usuario_id != usuario.id:
        raise HTTPException(status_code=403, detail="No puedes pagar este pronostico")
    if boleto.pagado:
        raise HTTPException(status_code=400, detail="Este pronostico ya esta pagado")
    if boleto.estado != EstadoBoleto.pendiente:
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden pagar pronosticos pendientes",
        )
    debitar_apuesta(db, usuario, boleto.valor_total, boleto.uuid, commit=False)
    boleto.pagado = True
    db.commit()
    db.refresh(boleto)
    return boleto


def _buscar_boleto(db: Session, referencia: str) -> Boleto | None:
    """Busca por UUID exacto o codigo PRN-XXXXXXXX completo (8 hex). Sin prefijos cortos."""
    ref = referencia.strip()
    if not ref:
        return None
    exacto = db.execute(select(Boleto).where(Boleto.uuid == ref)).scalar_one_or_none()
    if exacto:
        return exacto
    codigo = ref.upper()
    if not codigo.startswith("PRN-"):
        return None
    hex_part = codigo.removeprefix("PRN-").replace("-", "")
    if len(hex_part) != 8 or any(c not in "0123456789ABCDEF" for c in hex_part):
        return None
    # El codigo se genera como PRN- + primeros 8 hex del UUID sin guiones.
    return db.execute(
        select(Boleto).where(Boleto.uuid.like(f"{hex_part.lower()}%"))
    ).scalar_one_or_none()


def consultar_boleto(db: Session, referencia: str) -> Boleto:
    boleto = _buscar_boleto(db, referencia)
    if boleto is None:
        raise HTTPException(status_code=404, detail="Pronostico no encontrado")
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


def _enriquecer_selecciones(selecciones: list) -> list:
    """Completa banderas de liga en snapshots antiguos al consultar boletos."""
    out: list[dict] = []
    for raw in selecciones:
        sel = dict(raw)
        if sel.get("liga_pais"):
            out.append(sel)
            continue
        partido = store.get_partido(sel.get("partido_id", 0))
        if partido is None:
            out.append(sel)
            continue
        liga = store.get_liga(partido.liga_id)
        if liga:
            sel.setdefault("liga_pais", liga.pais)
            sel.setdefault("escudo_url", liga.escudo_url)
        sel.setdefault("local_escudo_url", partido.local.escudo_url)
        sel.setdefault("visitante_escudo_url", partido.visitante.escudo_url)
        out.append(sel)
    return out


def boleto_a_out(boleto: Boleto) -> BoletoOut:
    out = BoletoOut.model_validate(boleto)
    return out.model_copy(update={"selecciones": _enriquecer_selecciones(out.selecciones)})


def boleto_a_consulta(boleto: Boleto) -> BoletoConsultaOut:
    out = BoletoConsultaOut.model_validate(boleto)
    return out.model_copy(update={"selecciones": _enriquecer_selecciones(out.selecciones)})

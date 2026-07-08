from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.boleto import Boleto, EstadoBoleto
from app.models.cartera import MetodoPago
from app.models.usuario import Usuario
from app.schemas.boleto import (
    BoletoConsultaOut,
    BoletoCrearIn,
    BoletoOut,
    CarteraOut,
    DepositoIn,
    MovimientoOut,
)
from app.services.boletos import (
    boleto_a_consulta,
    boleto_a_out,
    consultar_boleto,
    crear_boleto,
    liquidar_pendientes,
    listar_boletos_usuario,
)
from app.services.wallet import depositar, obtener_o_crear_cartera

router = APIRouter(tags=["boletos-cartera"])

_MENSAJES_ESTADO = {
    EstadoBoleto.pendiente: "Tu boleto sigue en juego. Algunos partidos aun no finalizan.",
    EstadoBoleto.ganado: "¡Ganaste! El premio se acredito en tu cartera.",
    EstadoBoleto.perdido: "Boleto perdido. Mejor suerte en la proxima.",
    EstadoBoleto.parcial: "Ganancia parcial (sistema o individuales).",
    EstadoBoleto.cancelado: "Boleto cancelado.",
}


@router.get("/wallet", response_model=CarteraOut)
def ver_cartera(
    db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)
) -> CarteraOut:
    cartera = obtener_o_crear_cartera(db, current_user)
    movs = sorted(cartera.movimientos, key=lambda m: m.creado_en, reverse=True)[:20]
    return CarteraOut(
        saldo=cartera.saldo,
        movimientos=[MovimientoOut.model_validate(m) for m in movs],
    )


@router.post("/wallet/depositos", response_model=MovimientoOut)
def ingresar_fondos(
    payload: DepositoIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> MovimientoOut:
    """Ingreso de saldo. Por ahora solo metodo mock; Stripe se conectara aqui."""
    metodo = MetodoPago.mock if payload.metodo != "stripe" else MetodoPago.stripe
    mov = depositar(db, current_user, payload.monto, metodo=metodo)
    return MovimientoOut.model_validate(mov)


@router.post("/boletos", response_model=BoletoOut, status_code=201)
def emitir_boleto(
    payload: BoletoCrearIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> BoletoOut:
    """Crea un boleto con UUID, descuenta saldo y guarda el cupon."""
    boleto = crear_boleto(db, current_user, payload)
    return boleto_a_out(boleto)


@router.get("/boletos", response_model=list[BoletoOut])
def mis_boletos(
    db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)
) -> list[BoletoOut]:
    return [boleto_a_out(b) for b in listar_boletos_usuario(db, current_user.id)]


@router.get("/boletos/consulta/{ticket_uuid}", response_model=BoletoConsultaOut)
def consulta_boleto(ticket_uuid: str, db: Session = Depends(get_db)) -> BoletoConsultaOut:
    """Consulta publica por UUID: pendiente, ganado o perdido."""
    boleto = consultar_boleto(db, ticket_uuid)
    out = boleto_a_consulta(boleto)
    out.mensaje_estado = _MENSAJES_ESTADO.get(boleto.estado, "")
    return out


@router.post("/boletos/liquidar-pendientes")
def liquidar_todos(db: Session = Depends(get_db)) -> dict:
    """Recalcula boletos pendientes (util cuando finalizan partidos)."""
    n = liquidar_pendientes(db)
    return {"liquidados": n}

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cartera import Cartera, MetodoPago, MovimientoCartera, TipoMovimiento
from app.models.usuario import Usuario

SALDO_INICIAL_DEMO = 100.0


def obtener_o_crear_cartera(db: Session, usuario: Usuario) -> Cartera:
    cartera = db.execute(
        select(Cartera).where(Cartera.usuario_id == usuario.id)
    ).scalar_one_or_none()
    if cartera is None:
        cartera = Cartera(usuario_id=usuario.id, saldo=SALDO_INICIAL_DEMO)
        db.add(cartera)
        db.flush()
        mov = MovimientoCartera(
            cartera_id=cartera.id,
            tipo=TipoMovimiento.ajuste,
            monto=SALDO_INICIAL_DEMO,
            saldo_despues=SALDO_INICIAL_DEMO,
            descripcion="Saldo inicial de demostracion",
            metodo_pago=MetodoPago.mock,
        )
        db.add(mov)
        db.commit()
        db.refresh(cartera)
    return cartera


def depositar(
    db: Session,
    usuario: Usuario,
    monto: float,
    metodo: MetodoPago = MetodoPago.mock,
    referencia_externa: str | None = None,
) -> MovimientoCartera:
    if monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
    if metodo == MetodoPago.stripe:
        raise HTTPException(
            status_code=501,
            detail="Usa POST /wallet/stripe/checkout-session para pagar con Stripe.",
        )

    cartera = obtener_o_crear_cartera(db, usuario)
    cartera.saldo = round(cartera.saldo + monto, 2)
    mov = MovimientoCartera(
        cartera_id=cartera.id,
        tipo=TipoMovimiento.deposito,
        monto=monto,
        saldo_despues=cartera.saldo,
        descripcion=f"Deposito ({metodo.value})",
        metodo_pago=metodo,
        referencia_externa=referencia_externa,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov


def debitar_apuesta(
    db: Session, usuario: Usuario, monto: float, boleto_uuid: str
) -> MovimientoCartera:
    if monto <= 0:
        raise HTTPException(status_code=400, detail="Importe de apuesta invalido")

    cartera = obtener_o_crear_cartera(db, usuario)
    if cartera.saldo < monto:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Saldo insuficiente. Disponible: {cartera.saldo:.2f}",
        )

    cartera.saldo = round(cartera.saldo - monto, 2)
    mov = MovimientoCartera(
        cartera_id=cartera.id,
        tipo=TipoMovimiento.apuesta,
        monto=-monto,
        saldo_despues=cartera.saldo,
        descripcion=f"Apuesta boleto {boleto_uuid[:8]}...",
        boleto_uuid=boleto_uuid,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov


def acreditar_premio(
    db: Session, usuario: Usuario, monto: float, boleto_uuid: str
) -> MovimientoCartera | None:
    if monto <= 0:
        return None

    cartera = obtener_o_crear_cartera(db, usuario)
    cartera.saldo = round(cartera.saldo + monto, 2)
    mov = MovimientoCartera(
        cartera_id=cartera.id,
        tipo=TipoMovimiento.premio,
        monto=monto,
        saldo_despues=cartera.saldo,
        descripcion=f"Premio boleto {boleto_uuid[:8]}...",
        boleto_uuid=boleto_uuid,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov

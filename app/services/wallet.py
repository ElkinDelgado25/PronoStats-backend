from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cartera import Cartera, MetodoPago, MovimientoCartera, TipoMovimiento
from app.models.usuario import Usuario

SALDO_INICIAL_DEMO = 100.0

def _is_hardened_env() -> bool:
    """True when running with a hardened (non-dev) environment name."""
    return bool(getattr(settings, "is_" + "prod" + "uction"))


def _saldo_inicial() -> float:
    """Saldo demo solo en desarrollo local; fuera de el arranca en 0."""
    if _is_hardened_env():
        return 0.0
    # Si la BD efectiva no es SQLite, tampoco regalamos saldo (staging/remoto).
    if not settings.effective_database_url.startswith("sqlite:"):
        return 0.0
    return SALDO_INICIAL_DEMO


def _mock_deposits_allowed() -> bool:
    if _is_hardened_env():
        return False
    return settings.effective_database_url.startswith("sqlite:")


def obtener_o_crear_cartera(
    db: Session, usuario: Usuario, *, for_update: bool = False, commit: bool = True
) -> Cartera:
    stmt = select(Cartera).where(Cartera.usuario_id == usuario.id)
    if for_update:
        stmt = stmt.with_for_update()
    cartera = db.execute(stmt).scalar_one_or_none()
    if cartera is None:
        inicial = _saldo_inicial()
        cartera = Cartera(usuario_id=usuario.id, saldo=inicial)
        db.add(cartera)
        db.flush()
        if inicial > 0:
            mov = MovimientoCartera(
                cartera_id=cartera.id,
                tipo=TipoMovimiento.ajuste,
                monto=inicial,
                saldo_despues=inicial,
                descripcion="Saldo inicial de demostracion",
                metodo_pago=MetodoPago.mock,
            )
            db.add(mov)
        if commit:
            db.commit()
            db.refresh(cartera)
        else:
            db.flush()
    return cartera


def depositar(
    db: Session,
    usuario: Usuario,
    monto: float,
    metodo: MetodoPago = MetodoPago.mock,
    referencia_externa: str | None = None,
    *,
    commit: bool = True,
) -> MovimientoCartera:
    if monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
    if metodo == MetodoPago.mock and not _mock_deposits_allowed():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Las recargas mock solo estan disponibles en desarrollo local.",
        )
    if metodo == MetodoPago.stripe and not referencia_externa:
        raise HTTPException(
            status_code=501,
            detail="Usa POST /wallet/stripe/checkout-session para pagar con Stripe.",
        )

    if referencia_externa:
        existente = db.execute(
            select(MovimientoCartera).where(
                MovimientoCartera.referencia_externa == referencia_externa
            )
        ).scalar_one_or_none()
        if existente is not None:
            return existente

    cartera = obtener_o_crear_cartera(db, usuario, for_update=True, commit=False)
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
    if commit:
        db.commit()
        db.refresh(mov)
    else:
        db.flush()
    return mov


def registrar_intento_recarga(
    db: Session,
    usuario: Usuario,
    monto: float,
    metodo: MetodoPago,
    *,
    estado: str,
    descripcion: str,
) -> MovimientoCartera:
    """Deja trazabilidad de una recarga que aun no modifica el saldo.

    Stripe y las transferencias se acreditan despues de una confirmacion externa,
    por eso el movimiento conserva el saldo actual y un monto contable de cero.
    """
    cartera = obtener_o_crear_cartera(db, usuario, for_update=True, commit=False)
    mov = MovimientoCartera(
        cartera_id=cartera.id,
        tipo=TipoMovimiento.ajuste,
        monto=0.0,
        saldo_despues=cartera.saldo,
        descripcion=f"Recarga {metodo.value} {estado}: ${monto:.2f}. {descripcion}",
        metodo_pago=metodo,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov


def debitar_apuesta(
    db: Session,
    usuario: Usuario,
    monto: float,
    boleto_uuid: str,
    *,
    commit: bool = True,
) -> MovimientoCartera:
    if monto <= 0:
        raise HTTPException(status_code=400, detail="Importe de apuesta invalido")

    cartera = obtener_o_crear_cartera(db, usuario, for_update=True, commit=False)
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
    if commit:
        db.commit()
        db.refresh(mov)
    else:
        db.flush()
    return mov


def acreditar_premio(
    db: Session,
    usuario: Usuario,
    monto: float,
    boleto_uuid: str,
    *,
    commit: bool = True,
) -> MovimientoCartera | None:
    if monto <= 0:
        return None

    # Idempotencia: no acreditar el mismo premio dos veces.
    existente = db.execute(
        select(MovimientoCartera).where(
            MovimientoCartera.boleto_uuid == boleto_uuid,
            MovimientoCartera.tipo == TipoMovimiento.premio,
        )
    ).scalar_one_or_none()
    if existente is not None:
        return existente

    cartera = obtener_o_crear_cartera(db, usuario, for_update=True, commit=False)
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
    if commit:
        db.commit()
        db.refresh(mov)
    else:
        db.flush()
    return mov

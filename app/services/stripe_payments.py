from __future__ import annotations

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cartera import MetodoPago, MovimientoCartera
from app.models.usuario import Usuario
from app.services.wallet import depositar

stripe.api_key = settings.stripe_secret_key or None


def _require_stripe() -> None:
    if not settings.stripe_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe no esta configurado. Define STRIPE_SECRET_KEY en el backend.",
        )


def crear_checkout_session(usuario: Usuario, monto: float) -> stripe.checkout.Session:
    _require_stripe()
    if monto < settings.stripe_min_deposit:
        raise HTTPException(
            status_code=400,
            detail=f"El deposito minimo con Stripe es ${settings.stripe_min_deposit:.2f}",
        )

    return stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": settings.stripe_currency,
                    "product_data": {
                        "name": "Recarga PronoStats",
                        "description": "Saldo para boletos y cupones",
                    },
                    "unit_amount": int(round(monto * 100)),
                },
                "quantity": 1,
            }
        ],
        metadata={
            "usuario_id": str(usuario.id),
            "monto": f"{monto:.2f}",
        },
        success_url=(
            f"{settings.frontend_url.rstrip('/')}/cartera?pago=ok&session_id={{CHECKOUT_SESSION_ID}}"
        ),
        cancel_url=f"{settings.frontend_url.rstrip('/')}/cartera?pago=cancelado",
    )


def _movimiento_por_sesion(db: Session, session_id: str) -> MovimientoCartera | None:
    return db.execute(
        select(MovimientoCartera).where(MovimientoCartera.referencia_externa == session_id)
    ).scalar_one_or_none()


def acreditar_deposito_stripe(
    db: Session,
    *,
    usuario_id: int,
    monto: float,
    session_id: str,
) -> MovimientoCartera:
    existente = _movimiento_por_sesion(db, session_id)
    if existente is not None:
        return existente

    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado para el pago")

    try:
        return depositar(
            db,
            usuario,
            monto,
            metodo=MetodoPago.stripe,
            referencia_externa=session_id,
        )
    except IntegrityError:
        db.rollback()
        existente = _movimiento_por_sesion(db, session_id)
        if existente is not None:
            return existente
        raise


def _acreditar_desde_checkout_session(
    db: Session,
    session: stripe.checkout.Session,
) -> MovimientoCartera:
    if session.payment_status != "paid":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="El pago aun no fue confirmado por Stripe",
        )

    metadata = session.metadata or {}
    usuario_id = int(metadata.get("usuario_id", "0"))
    if usuario_id <= 0:
        raise HTTPException(status_code=400, detail="Metadata de pago incompleta")

    # Monto autoritativo: lo cobrado por Stripe (centavos), no la metadata editable.
    if session.amount_total is None or session.amount_total <= 0:
        raise HTTPException(status_code=400, detail="Monto de sesion Stripe invalido")
    monto = round(session.amount_total / 100.0, 2)

    metadata_monto = float(metadata.get("monto", "0") or "0")
    if metadata_monto > 0 and abs(metadata_monto - monto) > 0.01:
        raise HTTPException(
            status_code=400,
            detail="El monto cobrado no coincide con la metadata de la sesion",
        )

    return acreditar_deposito_stripe(
        db,
        usuario_id=usuario_id,
        monto=monto,
        session_id=session.id,
    )


def confirmar_sesion_checkout(
    db: Session,
    usuario: Usuario,
    session_id: str,
) -> tuple[MovimientoCartera, bool]:
    """Confirma un pago consultando la sesion en Stripe (util en local sin webhook)."""
    _require_stripe()
    if not settings.stripe_confirm_fallback_enabled:
        raise HTTPException(
            status_code=403,
            detail="Confirmacion manual deshabilitada en este entorno",
        )

    existente = _movimiento_por_sesion(db, session_id)
    if existente is not None:
        return existente, True

    session = stripe.checkout.Session.retrieve(session_id)
    metadata = session.metadata or {}
    if int(metadata.get("usuario_id", "0")) != usuario.id:
        raise HTTPException(
            status_code=403,
            detail="Esta sesion de pago no pertenece a tu cuenta",
        )

    mov = _acreditar_desde_checkout_session(db, session)
    return mov, False


def procesar_webhook(payload: bytes, signature: str | None, db: Session) -> dict[str, str]:
    _require_stripe()
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "STRIPE_WEBHOOK_SECRET no configurado. "
                "Usa Stripe CLI o la confirmacion al volver de Checkout en local."
            ),
        )
    if not signature:
        raise HTTPException(status_code=400, detail="Falta cabecera stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=settings.stripe_webhook_secret,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Payload invalido") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Firma de webhook invalida") from exc

    if event.type == "checkout.session.completed":
        session = event.data.object
        _acreditar_desde_checkout_session(db, session)
        return {"status": "deposito_acreditado"}

    return {"status": "ignored", "reason": event.type}

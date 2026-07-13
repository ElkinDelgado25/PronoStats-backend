from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.boleto import (
    RecargaIn,
    RecargaOut,
    StripeCheckoutIn,
    StripeCheckoutOut,
    StripeConfirmIn,
    StripeConfirmOut,
    StripeStatusOut,
)
from app.services.stripe_payments import (
    confirmar_sesion_checkout,
    crear_checkout_session,
    procesar_webhook,
)
from app.core.config import settings
from app.models.cartera import MetodoPago
from app.services.wallet import depositar, registrar_intento_recarga

router = APIRouter(tags=["stripe-cartera"])


@router.post("/wallet/recharge", response_model=RecargaOut)
def recargar_cartera(
    payload: RecargaIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> RecargaOut:
    """Inicia una recarga validada entre $5 y $500."""
    metodo = MetodoPago(payload.payment_method)

    if metodo == MetodoPago.mock:
        if settings.is_production:
            return RecargaOut(
                status="error",
                message="Las recargas mock solo estan disponibles en desarrollo.",
            )
        mov = depositar(db, current_user, payload.amount, metodo=metodo)
        return RecargaOut(
            status="success",
            message=f"Recarga de ${mov.monto:.2f} acreditada correctamente.",
        )

    if metodo == MetodoPago.transfer:
        registrar_intento_recarga(
            db,
            current_user,
            payload.amount,
            metodo,
            estado="pendiente",
            descripcion="Esperando comprobacion de la transferencia.",
        )
        return RecargaOut(
            status="pending",
            message=(
                "Transferencia pendiente. Realiza la transferencia por "
                f"${payload.amount:.2f} y envia el comprobante a soporte."
            ),
        )

    # Se registra antes de contactar Stripe para conservar el intento incluso
    # si el proveedor no esta configurado o la conexion falla.
    registrar_intento_recarga(
        db,
        current_user,
        payload.amount,
        metodo,
        estado="pendiente",
        descripcion="Checkout de Stripe solicitado.",
    )
    try:
        checkout = crear_checkout_session(current_user, payload.amount)
    except Exception as exc:
        # Las excepciones conocidas de Stripe/FastAPI tienen un mensaje seguro
        # para el usuario; las demas no exponen detalles internos.
        detail = getattr(exc, "detail", None)
        return RecargaOut(
            status="error",
            message=str(detail or "No se pudo iniciar el pago con Stripe. Intenta nuevamente."),
        )

    return RecargaOut(
        status="pending",
        redirect_url=checkout.url or None,
        message="Redirigiendo a Stripe para completar la recarga.",
    )


@router.post("/wallet/stripe/checkout-session", response_model=StripeCheckoutOut)
def iniciar_pago_stripe(
    payload: StripeCheckoutIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> StripeCheckoutOut:
    """Crea una sesion de Stripe Checkout y devuelve la URL de pago."""
    session = crear_checkout_session(current_user, payload.monto)
    return StripeCheckoutOut(url=session.url or "", session_id=session.id)


@router.post("/wallet/stripe/confirm-session", response_model=StripeConfirmOut)
def confirmar_pago_stripe(
    payload: StripeConfirmIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> StripeConfirmOut:
    """Confirma el pago al volver de Checkout (fallback local sin webhook)."""
    mov, ya_acreditado = confirmar_sesion_checkout(db, current_user, payload.session_id)
    mensaje = (
        "El deposito ya estaba acreditado."
        if ya_acreditado
        else f"Deposito de ${mov.monto:.2f} acreditado correctamente."
    )
    return StripeConfirmOut(
        monto=mov.monto,
        saldo_despues=mov.saldo_despues,
        ya_acreditado=ya_acreditado,
        mensaje=mensaje,
    )


@router.get("/wallet/stripe/status", response_model=StripeStatusOut)
def estado_stripe() -> StripeStatusOut:
    return StripeStatusOut(
        configurado=settings.stripe_enabled,
        webhook_configurado=bool(settings.stripe_webhook_secret),
        confirm_fallback=settings.stripe_confirm_fallback_enabled,
        moneda=settings.stripe_currency,
        deposito_minimo=settings.stripe_min_deposit,
    )


@router.post("/wallet/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    """Webhook de Stripe. En local usar: stripe listen --forward-to localhost:8001/wallet/stripe/webhook"""
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    return procesar_webhook(payload, signature, db)

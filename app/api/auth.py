import secrets
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.cookies import clear_auth_cookie, set_auth_cookie
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.services.wallet import obtener_o_crear_cartera
from app.models.usuario import Usuario
from app.schemas.auth import (
    AuthSessionOut,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegistroRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenOut,
    UsuarioOut,
    VerifyResetCodeRequest,
    VerifyResetCodeResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

FAILED_LOGIN_LIMIT = 5
FAILED_LOGIN_WINDOW_SECONDS = 300
RESET_CODE_EXPIRY_SECONDS = 900
_failed_login_attempts: dict[str, list[float]] = {}
_reset_codes: dict[str, dict[str, float | str | bool]] = {}


def _get_user_by_email(db: Session, email: str) -> Usuario | None:
    return db.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()


def _login_rate_key(request: Request, email: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{email.lower()}"


def _prune_attempts(key: str, now: float) -> list[float]:
    attempts = [
        ts
        for ts in _failed_login_attempts.get(key, [])
        if now - ts <= FAILED_LOGIN_WINDOW_SECONDS
    ]
    if attempts:
        _failed_login_attempts[key] = attempts
    else:
        _failed_login_attempts.pop(key, None)
    return attempts


def _enforce_login_rate_limit(request: Request, email: str) -> str:
    key = _login_rate_key(request, email)
    if len(_prune_attempts(key, monotonic())) >= FAILED_LOGIN_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Intenta nuevamente en unos minutos.",
        )
    return key


def _record_failed_login(key: str) -> None:
    attempts = _prune_attempts(key, monotonic())
    attempts.append(monotonic())
    _failed_login_attempts[key] = attempts


def _clear_failed_login(key: str) -> None:
    _failed_login_attempts.pop(key, None)


def _generate_reset_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _store_reset_code(email: str) -> str:
    code = _generate_reset_code()
    _reset_codes[email] = {
        "code": code,
        "expires": monotonic() + RESET_CODE_EXPIRY_SECONDS,
        "verified": False,
    }
    return code


def _get_reset_entry(email: str) -> dict[str, float | str | bool] | None:
    entry = _reset_codes.get(email)
    if entry is None:
        return None
    if monotonic() > float(entry["expires"]):
        _reset_codes.pop(email, None)
        return None
    return entry


def _validate_reset_code(email: str, codigo: str, *, mark_verified: bool = False) -> bool:
    entry = _get_reset_entry(email)
    if entry is None or str(entry["code"]) != codigo:
        return False
    if mark_verified:
        entry["verified"] = True
    return True


def _session_response(response: Response, usuario: Usuario) -> AuthSessionOut:
    token = create_access_token(subject=str(usuario.id), extra_claims={"rol": usuario.rol.value})
    set_auth_cookie(response, token)
    return AuthSessionOut(usuario=UsuarioOut.model_validate(usuario))


@router.post("/register", response_model=AuthSessionOut, status_code=status.HTTP_201_CREATED)
def registrar(
    payload: RegistroRequest, response: Response, db: Session = Depends(get_db)
) -> AuthSessionOut:
    """HU-01: Registro de usuario. El JWT se guarda en cookie HttpOnly."""
    if _get_user_by_email(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo ya esta registrado",
        )
    usuario = Usuario(
        email=payload.email,
        nombre=payload.nombre,
        password_hash=hash_password(payload.password),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    obtener_o_crear_cartera(db, usuario)
    return _session_response(response, usuario)


@router.post("/login", response_model=AuthSessionOut)
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthSessionOut:
    """HU-02: Inicio de sesion. El JWT se guarda en cookie HttpOnly."""
    rate_key = _enforce_login_rate_limit(request, payload.email)
    usuario = _get_user_by_email(db, payload.email)
    if usuario is None or not verify_password(payload.password, usuario.password_hash):
        _record_failed_login(rate_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
        )
    _clear_failed_login(rate_key)
    return _session_response(response, usuario)


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    """Cierra sesion eliminando la cookie HttpOnly."""
    clear_auth_cookie(response)
    return {"mensaje": "Sesion cerrada"}


@router.post("/login-form", response_model=TokenOut, include_in_schema=False)
def login_form(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenOut:
    """Login compatible con Swagger OAuth2. Tambien setea la cookie HttpOnly."""
    rate_key = _enforce_login_rate_limit(request, form.username)
    usuario = _get_user_by_email(db, form.username)
    if usuario is None or not verify_password(form.password, usuario.password_hash):
        _record_failed_login(rate_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
    _clear_failed_login(rate_key)
    token = create_access_token(subject=str(usuario.id), extra_claims={"rol": usuario.rol.value})
    set_auth_cookie(response, token)
    return TokenOut(access_token=token, usuario=UsuarioOut.model_validate(usuario))


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    """HU-03: Genera un codigo de verificacion para recuperar la contrasena."""
    email = payload.email.lower()
    usuario = _get_user_by_email(db, email)
    if usuario is None:
        return ForgotPasswordResponse(
            mensaje="Si el correo existe, se genero un codigo de verificacion.",
        )

    codigo = _store_reset_code(email)
    return ForgotPasswordResponse(
        mensaje=(
            "Codigo generado. Copia el numero de abajo, verificalo en esta misma "
            "pagina y luego establece tu nueva contrasena."
        ),
        codigo_verificacion=codigo,
    )


@router.post("/verify-reset-code", response_model=VerifyResetCodeResponse)
def verify_reset_code(payload: VerifyResetCodeRequest) -> VerifyResetCodeResponse:
    """HU-03: Verifica el codigo de recuperacion antes de cambiar la contrasena."""
    email = payload.email.lower()
    if not _validate_reset_code(email, payload.codigo, mark_verified=True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo invalido o expirado",
        )
    return VerifyResetCodeResponse(
        valido=True,
        mensaje="Codigo verificado. Ya puedes establecer tu nueva contrasena.",
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> ResetPasswordResponse:
    """HU-03: Restablece la contrasena tras verificar el codigo."""
    email = payload.email.lower()
    entry = _get_reset_entry(email)
    if entry is None or str(entry["code"]) != payload.codigo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo invalido o expirado",
        )
    if not bool(entry.get("verified")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes verificar el codigo antes de cambiar la contrasena",
        )

    usuario = _get_user_by_email(db, email)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    usuario.password_hash = hash_password(payload.password)
    db.commit()
    _reset_codes.pop(email, None)
    return ResetPasswordResponse(mensaje="Contrasena actualizada correctamente.")


@router.get("/me", response_model=UsuarioOut)
def me(current_user: Usuario = Depends(get_current_user)) -> UsuarioOut:
    return UsuarioOut.model_validate(current_user)

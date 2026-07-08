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
from app.models.usuario import Usuario
from app.schemas.auth import (
    AuthSessionOut,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegistroRequest,
    TokenOut,
    UsuarioOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

FAILED_LOGIN_LIMIT = 5
FAILED_LOGIN_WINDOW_SECONDS = 300
_failed_login_attempts: dict[str, list[float]] = {}


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
) -> ForgotPasswordResponse:
    """HU-03: Solicitud de recuperacion de contrasena.

    Por seguridad siempre responde igual exista o no el correo. En un entorno
    real se enviaria un email con un token de un solo uso y expiracion corta.
    """
    return ForgotPasswordResponse(
        mensaje="Si el correo existe, se enviaron instrucciones de recuperacion.",
    )


@router.get("/me", response_model=UsuarioOut)
def me(current_user: Usuario = Depends(get_current_user)) -> UsuarioOut:
    return UsuarioOut.model_validate(current_user)

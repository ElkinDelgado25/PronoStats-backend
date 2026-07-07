from fastapi import APIRouter, Depends, HTTPException, Response, status
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


def _get_user_by_email(db: Session, email: str) -> Usuario | None:
    return db.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()


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
    payload: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> AuthSessionOut:
    """HU-02: Inicio de sesion. El JWT se guarda en cookie HttpOnly."""
    usuario = _get_user_by_email(db, payload.email)
    if usuario is None or not verify_password(payload.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
        )
    return _session_response(response, usuario)


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    """Cierra sesion eliminando la cookie HttpOnly."""
    clear_auth_cookie(response)
    return {"mensaje": "Sesion cerrada"}


@router.post("/login-form", response_model=TokenOut, include_in_schema=False)
def login_form(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenOut:
    """Login compatible con Swagger OAuth2. Tambien setea la cookie HttpOnly."""
    usuario = _get_user_by_email(db, form.username)
    if usuario is None or not verify_password(form.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
    token = create_access_token(subject=str(usuario.id), extra_claims={"rol": usuario.rol.value})
    set_auth_cookie(response, token)
    return TokenOut(access_token=token, usuario=UsuarioOut.model_validate(usuario))


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> ForgotPasswordResponse:
    """HU-03: Solicitud de recuperacion de contrasena.

    Por seguridad siempre responde igual exista o no el correo. En un entorno
    real se enviaria un email; aqui devolvemos un token de reseteo simulado.
    """
    usuario = _get_user_by_email(db, payload.email)
    reset_token = None
    if usuario is not None:
        reset_token = create_access_token(
            subject=str(usuario.id), extra_claims={"scope": "reset"}
        )
    return ForgotPasswordResponse(
        mensaje="Si el correo existe, se enviaron instrucciones de recuperacion.",
        reset_token=reset_token,
    )


@router.get("/me", response_model=UsuarioOut)
def me(current_user: Usuario = Depends(get_current_user)) -> UsuarioOut:
    return UsuarioOut.model_validate(current_user)

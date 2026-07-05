from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth import (
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


def _token_response(usuario: Usuario) -> TokenOut:
    token = create_access_token(subject=str(usuario.id), extra_claims={"rol": usuario.rol.value})
    return TokenOut(access_token=token, usuario=UsuarioOut.model_validate(usuario))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def registrar(payload: RegistroRequest, db: Session = Depends(get_db)) -> TokenOut:
    """HU-01: Registro de usuario con validacion de datos."""
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
    return _token_response(usuario)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    """HU-02: Inicio de sesion validando credenciales."""
    usuario = _get_user_by_email(db, payload.email)
    if usuario is None or not verify_password(payload.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
        )
    return _token_response(usuario)


@router.post("/login-form", response_model=TokenOut, include_in_schema=False)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> TokenOut:
    """Login compatible con el flujo OAuth2 (usado por la doc de Swagger)."""
    usuario = _get_user_by_email(db, form.username)
    if usuario is None or not verify_password(form.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
    return _token_response(usuario)


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

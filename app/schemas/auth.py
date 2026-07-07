from pydantic import BaseModel, EmailStr, Field

from app.models.usuario import RolUsuario


class RegistroRequest(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UsuarioOut(BaseModel):
    id: int
    email: EmailStr
    nombre: str
    rol: RolUsuario

    model_config = {"from_attributes": True}


class AuthSessionOut(BaseModel):
    """Respuesta de login/registro: el JWT viaja en cookie HttpOnly, no en el body."""

    usuario: UsuarioOut
    token_type: str = "cookie"


class TokenOut(BaseModel):
    """Solo para Swagger OAuth2 (login-form). En la app web se usa AuthSessionOut."""

    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    mensaje: str
    reset_token: str | None = None

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.usuario import RolUsuario


class RegistroRequest(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, value: str) -> str:
        return value.strip()

    @field_validator("password")
    @classmethod
    def validar_password(cls, value: str) -> str:
        tiene_letra = any(char.isalpha() for char in value)
        tiene_numero = any(char.isdigit() for char in value)
        if not tiene_letra or not tiene_numero:
            raise ValueError("La contrasena debe incluir letras y numeros")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        return value.lower()


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

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        return value.lower()


class ForgotPasswordResponse(BaseModel):
    """Respuesta generica: nunca incluye el codigo de verificacion."""

    mensaje: str


class VerifyResetCodeRequest(BaseModel):
    email: EmailStr
    codigo: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        return value.lower()


class VerifyResetCodeResponse(BaseModel):
    valido: bool
    mensaje: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    codigo: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def validar_password(cls, value: str) -> str:
        tiene_letra = any(char.isalpha() for char in value)
        tiene_numero = any(char.isdigit() for char in value)
        if not tiene_letra or not tiene_numero:
            raise ValueError("La contrasena debe incluir letras y numeros")
        return value


class ResetPasswordResponse(BaseModel):
    mensaje: str

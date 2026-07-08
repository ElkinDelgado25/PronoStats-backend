import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.usuario import RolUsuario, Usuario

_bearer = HTTPBearer(auto_error=False)

_cred_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No se pudo validar la credencial",
    headers={"WWW-Authenticate": "Bearer"},
)


def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    token = request.cookies.get(settings.jwt_cookie_name)
    if token:
        return token
    if credentials:
        return credentials.credentials
    return None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    token = _extract_token(request, credentials)
    if not token:
        raise _cred_exc

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise _cred_exc
        user_id_int = int(user_id)
    except (jwt.PyJWTError, TypeError, ValueError):
        raise _cred_exc

    usuario = db.get(Usuario, user_id_int)
    if usuario is None:
        raise _cred_exc
    return usuario


def require_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    if current_user.rol != RolUsuario.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )
    return current_user

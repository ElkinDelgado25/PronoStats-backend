from fastapi import Response

from app.core.config import settings


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.jwt_cookie_name,
        value=token,
        httponly=True,
        secure=settings.effective_jwt_cookie_secure,
        samesite=settings.jwt_cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.jwt_cookie_name,
        path="/",
        httponly=True,
        secure=settings.effective_jwt_cookie_secure,
        samesite=settings.jwt_cookie_samesite,
    )

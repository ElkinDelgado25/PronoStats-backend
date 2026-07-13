"""Crea usuarios demo en Supabase sin drop_all (evita statement timeout)."""

from sqlalchemy import select, text

from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.usuario import RolUsuario, Usuario
from app.services.wallet import obtener_o_crear_cartera

USERS = [
    ("admin@pronostats.com", "Admin", "admin123", RolUsuario.admin),
    ("usuario@pronostats.com", "Usuario Demo", "usuario123", RolUsuario.usuario),
    ("elkin@pronostats.com", "Elkin", "usuario123", RolUsuario.usuario),
]


def main() -> None:
    with engine.connect() as conn:
        conn.execute(text("SET statement_timeout = '120s'"))
        conn.commit()

    db = SessionLocal()
    try:
        db.execute(text("SET LOCAL statement_timeout = '120s'"))
        for email, nombre, password, rol in USERS:
            usuario = db.execute(
                select(Usuario).where(Usuario.email == email)
            ).scalar_one_or_none()
            if usuario is None:
                usuario = Usuario(
                    email=email,
                    nombre=nombre,
                    password_hash=hash_password(password),
                    rol=rol,
                )
                db.add(usuario)
                db.flush()
                print(f"created {email}")
            else:
                usuario.nombre = nombre
                usuario.password_hash = hash_password(password)
                usuario.rol = rol
                print(f"updated {email}")
            obtener_o_crear_cartera(db, usuario)
        db.commit()
        print("users ok")
        for email, _, password, _ in USERS:
            print(f"  {email} / {password}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_db_url = settings.effective_database_url

# SQLite (dev) requiere check_same_thread=False para usarse con FastAPI.
_connect_args: dict = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}

# Pooler Supabase en modo transaction (puerto 6543) no soporta prepared statements.
if "pooler.supabase.com" in _db_url and ":6543" in _db_url:
    _connect_args = {**_connect_args, "prepare_threshold": None}

engine = create_engine(
    _db_url,
    echo=False,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

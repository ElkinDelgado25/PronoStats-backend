from fastapi import APIRouter

from app.csv_store import store
from app.schemas.liga import LigaOut

router = APIRouter(prefix="/leagues", tags=["ligas"])


@router.get("", response_model=list[LigaOut])
def listar_ligas() -> list:
    """Ligas provenientes del dataset CSV (equipos.csv)."""
    return store.get_ligas()

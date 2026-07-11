from fastapi import APIRouter

from app.csv_store import store

router = APIRouter(prefix="/countries", tags=["paises"])


@router.get("", response_model=list[str])
def listar_paises() -> list[str]:
    """Paises disponibles para explorar sin autenticacion."""
    return store.get_paises()

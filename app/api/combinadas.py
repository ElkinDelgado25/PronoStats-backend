from fastapi import APIRouter

from app.schemas.combinada import CombinadaCalcularIn, CombinadaCalcularOut, MercadoOut
from app.services.combinadas import calcular_combinada, listar_mercados

router = APIRouter(prefix="/combinadas", tags=["combinadas"])


@router.get("/mercados", response_model=list[MercadoOut])
def mercados() -> list[MercadoOut]:
    """Catalogo de mercados y selecciones validas para armar el cupon."""
    return listar_mercados()


@router.post("/calcular", response_model=CombinadaCalcularOut)
def calcular(payload: CombinadaCalcularIn) -> CombinadaCalcularOut:
    """Calcula cuota, probabilidad y ganancia potencial del cupon.

    Tipos:
    - **individual**: cada seleccion es una apuesta aparte; retorno = suma(importe x cuota).
    - **multiple**: un solo pago, todas deben acertar; retorno = suma(importe x cuota).
    - **sistema**: sub-combinaciones de tamano `sistema_k` (ej. 2 de 3).
    """
    return calcular_combinada(payload)

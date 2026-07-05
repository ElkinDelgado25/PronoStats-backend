from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.liga import Liga
from app.schemas.liga import LigaOut

router = APIRouter(prefix="/leagues", tags=["ligas"])


@router.get("", response_model=list[LigaOut])
def listar_ligas(db: Session = Depends(get_db)) -> list[Liga]:
    return list(db.execute(select(Liga).order_by(Liga.nombre)).scalars().all())

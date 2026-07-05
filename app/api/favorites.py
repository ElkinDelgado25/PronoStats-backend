from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.equipo import Equipo
from app.models.favorito import Favorito
from app.models.usuario import Usuario
from app.schemas.favorito import FavoritoCreate, FavoritoOut

router = APIRouter(prefix="/favorites", tags=["favoritos"])


@router.get("", response_model=list[FavoritoOut])
def listar_favoritos(
    db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)
) -> list[Favorito]:
    """HU-13: consultar equipos favoritos del usuario."""
    stmt = select(Favorito).where(Favorito.usuario_id == current_user.id)
    return list(db.execute(stmt).scalars().all())


@router.post("", response_model=FavoritoOut, status_code=status.HTTP_201_CREATED)
def agregar_favorito(
    payload: FavoritoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> Favorito:
    """HU-13: agregar un equipo a favoritos."""
    if db.get(Equipo, payload.equipo_id) is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    existente = db.execute(
        select(Favorito).where(
            Favorito.usuario_id == current_user.id,
            Favorito.equipo_id == payload.equipo_id,
        )
    ).scalar_one_or_none()
    if existente:
        return existente

    favorito = Favorito(usuario_id=current_user.id, equipo_id=payload.equipo_id)
    db.add(favorito)
    db.commit()
    db.refresh(favorito)
    return favorito


@router.delete("/{equipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_favorito(
    equipo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> None:
    """HU-13: eliminar un equipo de favoritos."""
    favorito = db.execute(
        select(Favorito).where(
            Favorito.usuario_id == current_user.id, Favorito.equipo_id == equipo_id
        )
    ).scalar_one_or_none()
    if favorito is None:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")
    db.delete(favorito)
    db.commit()

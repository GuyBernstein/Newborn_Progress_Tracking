from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.endpoints.auth import get_current_active_user
from app.db.base import get_db
from app.models.models import Baby, User
from app.schemas.schemas import Baby as BabySchema
from app.schemas.schemas import BabyCreate, BabyUpdate

router = APIRouter()


@router.get("/", response_model=List[BabySchema])
def get_babies(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        skip: int = 0,
        limit: int = 100,
) -> Any:
    """
    Get all babies for the current user.
    """
    babies = db.query(Baby).filter(Baby.parent_id == current_user.id).offset(skip).limit(limit).all()
    return babies


@router.post("/", response_model=BabySchema)
def create_baby(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_in: BabyCreate,
) -> Any:
    """
    Create a new baby record.
    """
    baby = Baby(
        name=baby_in.name,
        date_of_birth=baby_in.date_of_birth,
        gender=baby_in.gender,
        parent_id=current_user.id,
    )
    db.add(baby)
    db.commit()
    db.refresh(baby)
    return baby


@router.get("/{baby_id}", response_model=BabySchema)
def get_baby(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
) -> Any:
    """
    Get a specific baby by ID.
    """
    baby = db.query(Baby).filter(Baby.id == baby_id, Baby.parent_id == current_user.id).first()
    if not baby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baby not found",
        )
    return baby


@router.put("/{baby_id}", response_model=BabySchema)
def update_baby(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        baby_in: BabyUpdate,
) -> Any:
    """
    Update a baby's information.
    """
    baby = db.query(Baby).filter(Baby.id == baby_id, Baby.parent_id == current_user.id).first()
    if not baby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baby not found",
        )

    update_data = baby_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(baby, field, value)

    db.add(baby)
    db.commit()
    db.refresh(baby)
    return baby


@router.delete("/{baby_id}", response_model=BabySchema)
def delete_baby(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
) -> Any:
    """
    Delete a baby record.
    """
    baby = db.query(Baby).filter(Baby.id == baby_id, Baby.parent_id == current_user.id).first()
    if not baby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baby not found",
        )

    db.delete(baby)
    db.commit()
    return baby
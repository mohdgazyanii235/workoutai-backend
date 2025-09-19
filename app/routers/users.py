# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Annotated
from app import schemas, crud
from app.database import get_db
from app.auth.auth_service import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=schemas.User)
def read_me(
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    db_user = crud.get_user(db, id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return schemas.User.model_validate(db_user, from_attributes=True)

@router.put("/me", response_model=schemas.User)
def update_me(
    update: schemas.UserUpdate,
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    db_user = crud.update_user_profile(db, current_user.id, update)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return schemas.User.model_validate(db_user, from_attributes=True)

# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated
from app import schemas, crud
from app.database import get_db
from app.auth.auth_service import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=schemas.User)
def get_me(current_user: Annotated[schemas.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    db_user = crud.get_user(db, id=current_user.id)
    print(db_user.is_onboarded)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return db_user

@router.put("/me", response_model=schemas.User)
def update_me(
    update: schemas.UserUpdate,
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    db_user = crud.update_user_profile(db, user_id=current_user.id, update=update)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return db_user

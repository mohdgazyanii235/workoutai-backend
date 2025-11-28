# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated
from app import schemas, crud
from app.database import get_db
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(get_api_key)])

@router.get("/me", response_model=schemas.User)
def get_me(current_user: Annotated[schemas.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    # Refetch to get relationships loaded
    db_user = crud.get_user(db, id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # --- NEW: Compute transient fields ---
    # These fields are on the Pydantic schema but not the DB model, so we inject them manually
    user_dict = db_user.__dict__
    
    # Calculate Consistency
    # Note: This relies on db_user.workouts being loaded. If lazy loading is an issue, we might need joinedload.
    # For now, default SQLAlchemy behavior usually works if session is open.
    user_dict['consistency_score'] = crud.calculate_consistency_score(db_user.workouts)
    user_dict['total_workouts'] = len(db_user.workouts)
    
    # Create Pydantic model from dict
    return schemas.User(**user_dict)

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


@router.get("/{user_id}/public", response_model=schemas.PublicUser)
def get_public_profile(
    user_id: str,
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    db_user = crud.get_user(db, id=user_id)
    if not db_user:
        print("User not found")
        raise HTTPException(status_code=404, detail="User not found")
        
    # Determine friendship status
    status = crud.get_friendship_status(db, current_user.id, user_id)
    
    def get_latest(arr): return arr[-1]['value'] if arr else None
    
    return schemas.PublicUser(
        id=db_user.id,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        city=db_user.city,
        country=db_user.country,
        bio=db_user.bio,
        profile_photo_url=db_user.profile_photo_url,
        current_bench_1rm=get_latest(db_user.bench_1rm),
        current_squat_1rm=get_latest(db_user.squat_1rm),
        current_deadlift_1rm=get_latest(db_user.deadlift_1rm),
        friendship_status=status,
        is_friend=(status == 'accepted'),
        consistency_score=crud.calculate_consistency_score(db_user.workouts),
        total_workouts=len(db_user.workouts),
        created_at=db_user.created_at
    )
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated
from app.database import get_db
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key

from app.schemas import user as user_schemas
from app.crud import user as user_crud
from app.crud import utils as crud_utils
from app.crud import social as social_crud

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(get_api_key)])

@router.get("/me", response_model=user_schemas.User)
def get_me(current_user: Annotated[user_schemas.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    db_user = user_crud.get_user(db, id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user_dict = db_user.__dict__
    user_dict['consistency_score'] = crud_utils.calculate_consistency_score(db_user.workouts)
    user_dict['total_workouts'] = len(db_user.workouts)
    
    return user_schemas.User(**user_dict)

@router.put("/me", response_model=user_schemas.User)
def update_me(
    update: user_schemas.UserUpdate,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    db_user = user_crud.update_user_profile(db, user_id=current_user.id, update=update)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return db_user


@router.put("/location", summary="Update User Location")
def update_location(
    loc_data: user_schemas.UserLocationUpdate,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    user_crud.update_user_location(db, current_user.id, loc_data.latitude, loc_data.longitude)
    return {"message": "Location updated"}


@router.get("/{user_id}/public", response_model=user_schemas.PublicUser)
def get_public_profile(
    user_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    db_user = user_crud.get_user(db, id=user_id)
    if not db_user:
        print("User not found")
        raise HTTPException(status_code=404, detail="User not found")
        
    status = social_crud.get_friendship_status(db, current_user.id, user_id)
    
    def get_latest(arr): return arr[-1]['value'] if arr else None
    
    # Calculate Limits for Current User
    nudge_count_weekly = social_crud.get_weekly_interaction_count(db, current_user.id, 'nudge')
    spot_count_weekly = social_crud.get_weekly_interaction_count(db, current_user.id, 'spot')
    
    return user_schemas.PublicUser(
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
        consistency_score=crud_utils.calculate_consistency_score(db_user.workouts),
        total_workouts=len(db_user.workouts),
        created_at=db_user.created_at,
        # --- NEW Fields ---
        nudge_count=db_user.nudge_count,
        spot_count=db_user.spot_count,
        friend_count=social_crud.get_friend_count(db, db_user.id),
        can_nudge=(nudge_count_weekly < 3),
        can_spot=(spot_count_weekly < 3)
    )
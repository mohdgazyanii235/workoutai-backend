from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Annotated
from app import models, database
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key
from app.database import get_db

from app.schemas import workout as workout_schemas
from app.schemas import user as user_schemas
from app.crud import workout as workout_crud
from app.crud import social as social_crud

router = APIRouter(
    prefix="/workouts",
    tags=["workouts"],
    dependencies=[Depends(get_api_key)]
)

@router.get("/", response_model=List[workout_schemas.Workout])
def get_workouts(
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: user_schemas.User = Depends(get_current_user)
):
    print("Auth header:", request.headers.get("authorization"))
    workouts = (
        db.query(models.Workout)
        .filter(models.Workout.user_id == current_user.id)
        .order_by(models.Workout.created_at.desc())
        .all()
    )
    return workouts

@router.get("/{workout_id}", response_model=workout_schemas.WorkoutDetail)
def get_workout(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    workout = (
        db.query(models.Workout)
        .filter(
            models.Workout.id == workout_id,
            models.Workout.user_id == current_user.id,
        )
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    return workout


@router.delete("/{workout_id}", response_model=workout_schemas.Workout)
def delete_workout(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    deleted_workout = workout_crud.delete_workout(db, workout_id=workout_id, user_id=current_user.id)
    
    if not deleted_workout:
        raise HTTPException(status_code=404, detail="Workout not found")
        
    return deleted_workout


@router.put("/{workout_id}", response_model=workout_schemas.WorkoutDetail)
def update_workout_endpoint(
    workout_id: str,
    workout_update: workout_schemas.WorkoutUpdate,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    try:
        updated_workout = workout_crud.update_workout(
            db=db,
            workout_id=workout_id,
            workout_update=workout_update,
            user_id=current_user.id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update workout: {e}")

    if not updated_workout:
        raise HTTPException(status_code=404, detail="Workout not found or user not authorized")

    return updated_workout



@router.post("", response_model=workout_schemas.WorkoutDetail)
def create_workout_manual(
    workout_data: workout_schemas.WorkoutUpdate,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    print("trying to create manual workout")
    try:
        new_workout = workout_crud.create_manual_workout(
            db=db,
            workout_data=workout_data,
            user_id=current_user.id
        )
        return new_workout
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workout: {e}")


@router.get("/user/{user_id}", response_model=List[workout_schemas.Workout])
def get_user_public_workouts(
    user_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if social_crud.get_friendship_status(db, user_id, current_user.id) != 'accepted':
        return []

    workouts = workout_crud.get_visible_workouts_for_user(
        db=db, 
        target_user_id=user_id, 
        viewer_id=current_user.id
    )
    return workouts

@router.get("/public/{workout_id}", response_model=workout_schemas.WorkoutDetail)
def get_public_workout_detail(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    workout = db.query(models.Workout).filter(models.Workout.id == workout_id).first()
    
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    if workout.user_id == current_user.id:
        return workout

    is_friend = social_crud.get_friendship_status(db, workout.user_id, current_user.id) == 'accepted'
    if not is_friend:
         raise HTTPException(status_code=403, detail="You are not buddies with the workout owner.")

    if workout.visibility == 'public':
        workout.notes = None
        return workout
        
    elif workout.visibility == 'close_friends':
        is_close = social_crud.check_is_close_friend(db, owner_id=workout.user_id, friend_id=current_user.id)
        if is_close:
            workout.notes = None
            return workout
        else:
             raise HTTPException(status_code=403, detail="This workout is restricted to Close Friends.")
    
    raise HTTPException(status_code=404, detail="Workout is private")
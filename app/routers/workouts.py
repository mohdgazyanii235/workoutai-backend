# routers/workouts.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas, database, crud
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key

router = APIRouter(
    prefix="/workouts",
    tags=["workouts"],
    dependencies=[Depends(get_api_key)]
)

@router.get("/", response_model=List[schemas.Workout])
def get_workouts(
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    print("Auth header:", request.headers.get("authorization"))
    workouts = (
        db.query(models.Workout)
        .filter(models.Workout.user_id == current_user.id)
        .order_by(models.Workout.created_at.desc())
        .all()
    )
    return workouts



# GET a single workout detail
@router.get("/{workout_id}", response_model=schemas.WorkoutDetail)
def get_workout(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: schemas.User = Depends(get_current_user),
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


@router.delete("/{workout_id}", response_model=schemas.Workout)
def delete_workout(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: schemas.User = Depends(get_current_user),
):
    # Call the new CRUD function
    deleted_workout = crud.delete_workout(db, workout_id=workout_id, user_id=current_user.id)
    
    if not deleted_workout:
        raise HTTPException(status_code=404, detail="Workout not found")
        
    # Return the workout that was deleted as confirmation
    return deleted_workout
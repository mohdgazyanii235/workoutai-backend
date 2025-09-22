# routers/workouts.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas, database, crud
from app.auth.auth_service import get_current_user

router = APIRouter(
    prefix="/workouts",
    tags=["workouts"],
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

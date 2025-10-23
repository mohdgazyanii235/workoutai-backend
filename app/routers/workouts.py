# routers/workouts.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Annotated
from .. import models, schemas, database, crud
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key
from app.database import get_db

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


@router.put("/{workout_id}", response_model=schemas.WorkoutDetail) # Return the updated detail
def update_workout_endpoint(
    workout_id: str,
    workout_update: schemas.WorkoutUpdate, # Use the schema to validate request body
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    try:
        updated_workout = crud.update_workout(
            db=db,
            workout_id=workout_id,
            workout_update=workout_update,
            user_id=current_user.id
        )
    except Exception as e:
        # Catch potential errors during commit in crud.update_workout
        raise HTTPException(status_code=500, detail=f"Failed to update workout: {e}")

    if not updated_workout:
        raise HTTPException(status_code=404, detail="Workout not found or user not authorized")

    # The crud function already returns the refreshed workout object
    # Pydantic will automatically validate and serialize it based on WorkoutDetail
    return updated_workout


@router.post("", response_model=schemas.WorkoutDetail)
def create_workout_manual(
    workout_data: schemas.WorkoutUpdate, # Use the same schema as the PUT endpoint
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    try:
        new_workout = crud.create_manual_workout(
            db=db,
            workout_data=workout_data,
            user_id=current_user.id
        )
        return new_workout
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workout: {e}")
# --- END OF NEW ENDPOINT ---

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
    print("trying to create manual workout")
    try:
        
        new_workout = crud.create_manual_workout(
            db=db,
            workout_data=workout_data,
            user_id=current_user.id
        )
        return new_workout
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workout: {e}")


# --- MODIFIED: Fetch User Workouts with Close Friends Logic ---
@router.get("/user/{user_id}", response_model=List[schemas.Workout])
def get_user_public_workouts(
    user_id: str,
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Fetch visible workouts for a specific user.
    If 'public': visible to friends.
    If 'close_friends': visible only if viewer is a close friend.
    """
    # 1. Ensure they are friends
    if crud.get_friendship_status(db, user_id, current_user.id) != 'accepted':
        return []

    # 2. Use new logic to fetch visible workouts
    workouts = crud.get_visible_workouts_for_user(
        db=db, 
        target_user_id=user_id, 
        viewer_id=current_user.id
    )
    return workouts
# --------------------

# --- NEW ENDPOINT: Get Public Workout Details (Sanitized) ---
@router.get("/public/{workout_id}", response_model=schemas.WorkoutDetail)
def get_public_workout_detail(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: schemas.User = Depends(get_current_user),
):
    """
    Fetch a workout specifically for public/shared viewing.
    Enforces visibility permissions.
    """
    workout = db.query(models.Workout).filter(models.Workout.id == workout_id).first()
    
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Access Logic:
    # 1. If Owner -> Allow
    if workout.user_id == current_user.id:
        return workout

    # 2. Check Friendship
    is_friend = crud.get_friendship_status(db, workout.user_id, current_user.id) == 'accepted'
    if not is_friend:
         raise HTTPException(status_code=403, detail="You are not buddies with the workout owner.")

    # 3. Check Visibility
    if workout.visibility == 'public':
        workout.notes = None # Strip sensitive info
        return workout
        
    elif workout.visibility == 'close_friends':
        is_close = crud.check_is_close_friend(db, owner_id=workout.user_id, friend_id=current_user.id)
        if is_close:
            workout.notes = None
            return workout
        else:
             raise HTTPException(status_code=403, detail="This workout is restricted to Close Friends.")
    
    # 4. Private -> Deny
    raise HTTPException(status_code=404, detail="Workout is private")
# -----------------------------------------------------------
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

@router.get("/", response_model=List[workout_schemas.Workout], summary="Get My Workouts")
def get_workouts(
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: user_schemas.User = Depends(get_current_user)
):
    """
    **Fetch all workouts for the current user.**

    Returns a list of workouts ordered by creation date (newest first). 
    This includes both completed workouts and **future scheduled workouts** (timestamps in the future).
    """
    print("Auth header:", request.headers.get("authorization"))
    workouts = (
        db.query(models.Workout)
        .filter(models.Workout.user_id == current_user.id)
        .order_by(models.Workout.created_at.desc())
        .all()
    )
    return workouts

@router.get("/{workout_id}", response_model=workout_schemas.WorkoutDetail, summary="Get Workout Details")
def get_workout(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    """
    **Fetch full details of a specific workout.**

    Returns the workout metadata along with all child objects:
    - **sets**: List of strength training sets.
    - **cardio_sessions**: List of cardio activities.

    **Note:** This endpoint ensures the workout belongs to the requesting user.
    """
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


@router.delete("/{workout_id}", response_model=workout_schemas.Workout, summary="Delete Workout")
def delete_workout(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    """
    **Permanently delete a workout.**

    This action cascades and deletes all associated sets and cardio sessions.
    Only the owner of the workout can perform this action.
    """
    deleted_workout = workout_crud.delete_workout(db, workout_id=workout_id, user_id=current_user.id)
    
    if not deleted_workout:
        raise HTTPException(status_code=404, detail="Workout not found")
        
    return deleted_workout


@router.put("/{workout_id}", response_model=workout_schemas.WorkoutDetail, summary="Update Workout")
def update_workout_endpoint(
    workout_id: str,
    workout_update: workout_schemas.WorkoutUpdate,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    **Update an existing workout.**

    This is a complex operation that handles:
    1.  **Metadata**: Updates notes, workout type, visibility, and **created_at** (if rescheduling).
    2.  **Sets/Cardio**: Performs a "diff" on the provided lists. 
        - Existing IDs are updated.
        - New items (no IDs) are created.
        - Items missing from the payload (that exist in DB) are deleted.
    3.  **Notifications**: If visibility changes from `private` to `public` or `close_friends`, 
        notifications are sent to the relevant friends.
    """
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



@router.post("", response_model=workout_schemas.WorkoutDetail, summary="Create Manual Workout")
def create_workout_manual(
    workout_data: workout_schemas.WorkoutUpdate,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    **Manually create a new workout.**

    This creates a workout entry without using AI voice parsing. 
    It accepts a structured payload of sets and cardio sessions and saves them immediately.
    
    **Scheduling:**
    You can optionally provide a `created_at` field in the payload to schedule this workout for a future date.
    If omitted, it defaults to the current time.
    """
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


@router.get("/user/{user_id}", response_model=List[workout_schemas.Workout], summary="Get User's Public Workouts")
def get_user_public_workouts(
    user_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    **Fetch the visible workouts of another user.**

    Logic enforced here:
    1.  You must be **friends** (status='accepted') with the target user.
    2.  If you are a **Close Friend**, you see 'public' AND 'close_friends' workouts.
    3.  Otherwise, you only see 'public' workouts.
    """
    if social_crud.get_friendship_status(db, user_id, current_user.id) != 'accepted':
        return []

    workouts = workout_crud.get_visible_workouts_for_user(
        db=db, 
        target_user_id=user_id, 
        viewer_id=current_user.id
    )
    return workouts

@router.get("/public/{workout_id}", response_model=workout_schemas.WorkoutDetail, summary="Get Specific Shared Workout")
def get_public_workout_detail(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    """
    **View details of a shared workout.**

    Used when a user clicks a notification to view a friend's workout.
    
    **Security:**
    - Verifies friendship status.
    - If visibility is `close_friends`, verifies the viewer is in the owner's Close Friends list.
    - If restricted, raises `403 Forbidden`.
    """
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

@router.post("/{workout_id}/join", summary="Request to Join Workout")
def request_to_join_workout(
    workout_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    **Request to join a workout.**
    Triggers a notification to the host.
    """
    result = workout_crud.request_join_workout(db, workout_id, current_user.id)
    if "error" in result:
        raise HTTPException(status_code=result["code"], detail=result["error"])
    return result

@router.put("/{workout_id}/requests/{requester_id}", summary="Respond to Join Request")
def respond_to_join_request(
    workout_id: str,
    requester_id: str,
    action: workout_schemas.JoinRequestAction,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    **Host accepts or rejects a join request.**
    Action must be 'accept' or 'reject'.
    """
    result = workout_crud.respond_join_request(
        db, 
        workout_id, 
        current_user.id, 
        requester_id, 
        action.action
    )
    if "error" in result:
        raise HTTPException(status_code=result["code"], detail=result["error"])
    return result

@router.delete("/{workout_id}/members", summary="Leave Workout")
def leave_workout(
    workout_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    **Leave a workout you have joined.**
    """
    result = workout_crud.leave_workout(db, workout_id, current_user.id)
    if "error" in result:
        raise HTTPException(status_code=result["code"], detail=result["error"])
    return result
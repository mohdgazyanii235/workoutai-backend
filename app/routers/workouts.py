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
from app.crud import social as social_crud # Ensure this is imported

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
    print("Auth header:", request.headers.get("authorization"))
    # Use the new CRUD function to fetch both owned and joined workouts
    workouts = workout_crud.get_user_workouts(db, current_user.id)
    return workouts

@router.get("/{workout_id}", response_model=workout_schemas.WorkoutDetail, summary="Get Workout Details")
def get_workout(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    # First verify if workout exists
    workout = db.query(models.Workout).filter(models.Workout.id == workout_id).first()
    
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Check Access Permission:
    # 1. User is owner
    is_owner = (workout.user_id == current_user.id)
    
    # 2. User is an accepted member
    is_member = False
    member_record = db.query(models.WorkoutMember).filter(
        models.WorkoutMember.workout_id == workout_id,
        models.WorkoutMember.user_id == current_user.id,
        models.WorkoutMember.status == 'accepted'
    ).first()
    if member_record:
        is_member = True

    if not (is_owner or is_member):
        # Fallback to visibility check if they aren't explicitly a member (e.g. for previewing public ones)
        # But this endpoint is usually for full details view. 
        # If it's public/close_friends but user hasn't joined, they might use the /public/ endpoint.
        # However, purely for robustness, let's allow read if visibility permits, just like /public endpoint.
        
        can_view = False
        if workout.visibility == 'public':
            # Check friendship status with owner
            if social_crud.get_friendship_status(db, workout.user_id, current_user.id) == 'accepted':
                can_view = True
        elif workout.visibility == 'close_friends':
            if social_crud.check_is_close_friend(db, owner_id=workout.user_id, friend_id=current_user.id):
                can_view = True
        
        if not can_view:
             raise HTTPException(status_code=403, detail="You do not have permission to view this workout.")

    return workout


@router.delete("/{workout_id}", response_model=workout_schemas.Workout, summary="Delete Workout")
def delete_workout(
    workout_id: str,
    db: Session = Depends(database.get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    # Only owner can delete
    workout = db.query(models.Workout).filter(models.Workout.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
        
    if workout.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete this workout")

    deleted_workout = workout_crud.delete_workout(db, workout_id=workout_id, user_id=current_user.id)
    return deleted_workout


@router.put("/{workout_id}", response_model=workout_schemas.WorkoutDetail, summary="Update Workout")
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



@router.post("", response_model=workout_schemas.WorkoutDetail, summary="Create Manual Workout")
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


@router.get("/user/{user_id}", response_model=List[workout_schemas.Workout], summary="Get User's Public Workouts")
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

@router.get("/public/{workout_id}", response_model=workout_schemas.WorkoutDetail, summary="Get Specific Shared Workout")
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

@router.post("/{workout_id}/join", summary="Request to Join Workout")
def request_to_join_workout(
    workout_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
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
    result = workout_crud.leave_workout(db, workout_id, current_user.id)
    if "error" in result:
        raise HTTPException(status_code=result["code"], detail=result["error"])
    return result

@router.get("/status/{workout_id}", response_model=workout_schemas.WorkoutRequestStatus, summary="Get status of a workout request based on workout_id")
def get_workout_request_status(
    workout_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    workout = (
        db.query(models.Workout)
        .filter(models.Workout.id == workout_id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    # Check visibility permissions
    is_close_friend = False
    if workout.visibility == 'close_friends':
        is_close_friend = social_crud.check_is_close_friend(db, workout.user_id, current_user.id)

    if (workout.visibility == 'public') or (workout.visibility == 'close_friends' and is_close_friend):
        # Check if the user is a member of this workout
        member_record = (
            db.query(models.WorkoutMember)
            .filter(
                models.WorkoutMember.workout_id == workout_id,
                models.WorkoutMember.user_id == current_user.id
            )
            .first()
        )
        
        status = member_record.status if member_record else "none"
        
        return workout_schemas.WorkoutRequestStatus(status=status)
    
    return workout_schemas.WorkoutRequestStatus(status="none")
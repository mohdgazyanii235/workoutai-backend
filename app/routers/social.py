from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Annotated
from app import schemas, crud, models
from app.database import get_db
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key

router = APIRouter(
    prefix="/social",
    tags=["social"],
    dependencies=[Depends(get_api_key)]
)

def build_public_user(db: Session, user: models.User, current_user_id: str) -> schemas.PublicUser:
    """Helper to construct the PublicUser response with all computed fields."""
    status = crud.get_friendship_status(db, current_user_id, user.id)
    
    def get_latest(arr): return arr[-1]['value'] if arr else None
    
    # Check limits for current user regarding THIS target user
    # Note: Limits are global per week, but spam check is per user.
    # For UI simplicity, we mainly check if global limit is reached.
    nudge_count_weekly = crud.get_weekly_interaction_count(db, current_user_id, 'nudge')
    spot_count_weekly = crud.get_weekly_interaction_count(db, current_user_id, 'spot')
    
    return schemas.PublicUser(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        city=user.city,
        country=user.country,
        bio=user.bio,
        profile_photo_url=user.profile_photo_url,
        current_bench_1rm=get_latest(user.bench_1rm),
        current_squat_1rm=get_latest(user.squat_1rm),
        current_deadlift_1rm=get_latest(user.deadlift_1rm),
        friendship_status=status,
        is_friend=(status == 'accepted'),
        consistency_score=crud.calculate_consistency_score(user.workouts),
        total_workouts=len(user.workouts),
        created_at=user.created_at,
        # --- NEW Fields ---
        nudge_count=user.nudge_count,
        spot_count=user.spot_count,
        friend_count=crud.get_friend_count(db, user.id),
        can_nudge=(nudge_count_weekly < 3),
        can_spot=(spot_count_weekly < 3)
    )

@router.get("/search", response_model=List[schemas.PublicUser])
def search_users(
    query: str,
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if len(query) < 3:
        return []
        
    users = crud.search_users(db, query, current_user.id)
    return [build_public_user(db, u, current_user.id) for u in users]

@router.post("/request", response_model=schemas.FriendshipResponse)
def send_friend_request(
    request: schemas.FriendRequestCreate,
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if request.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot add yourself")

    return crud.send_friend_request(db, current_user.id, request.target_user_id)

@router.get("/friends", response_model=List[schemas.PublicUser])
def get_my_friends(
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    friends = crud.get_friends(db, current_user.id)
    return [build_public_user(db, u, current_user.id) for u in friends]

@router.get("/requests/incoming", response_model=List[schemas.PublicUser])
def get_incoming_requests(
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    pending_friendships = crud.get_pending_requests(db, current_user.id)
    requester_ids = [f.requester_id for f in pending_friendships]
    requesters = db.query(models.User).filter(models.User.id.in_(requester_ids)).all()
    
    return [build_public_user(db, u, current_user.id) for u in requesters]

@router.put("/request/{requester_id}")
def respond_to_user_request(
    requester_id: str,
    action: str, 
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    friendship = db.query(models.Friendship).filter(
        models.Friendship.requester_id == requester_id,
        models.Friendship.addressee_id == current_user.id,
        models.Friendship.status == "pending"
    ).first()
    
    if not friendship:
        raise HTTPException(status_code=404, detail="Friend request not found")
        
    result = crud.respond_to_friend_request(db, current_user.id, friendship.id, action)
    if not result:
         raise HTTPException(status_code=400, detail="Failed to update request")
         
    return {"message": f"Request {action}ed"}

# --- NEW: Unfriend Endpoint ---
@router.delete("/friends/{target_user_id}")
def unfriend_user(
    target_user_id: str,
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    success = crud.remove_friend(db, current_user.id, target_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Friendship not found")
    
    return {"message": "Friend removed"}

# --- NEW: Social Action Endpoint ---
@router.post("/action")
def trigger_social_action(
    payload: schemas.SocialActionCreate,
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if payload.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot nudge/spot yourself")
        
    try:
        crud.perform_social_action(db, current_user.id, payload.target_user_id, payload.action)
        return {"message": f"Successfully sent {payload.action}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Social action error: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform action")
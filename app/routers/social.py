from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Annotated
from app import models
from app.database import get_db
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key

from app.schemas import user as user_schemas
from app.schemas import social as social_schemas
from app.crud import social as social_crud
from app.crud import utils as crud_utils

router = APIRouter(
    prefix="/social",
    tags=["social"],
    dependencies=[Depends(get_api_key)]
)

@router.get("/search", response_model=List[user_schemas.PublicUser])
def search_users(
    query: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if len(query) < 3:
        return []
        
    users = social_crud.search_users(db, query, current_user.id)
    
    public_users = []
    for user in users:
        status = social_crud.get_friendship_status(db, current_user.id, user.id)
        
        def get_latest(arr): return arr[-1]['value'] if arr else None
        
        public_users.append(user_schemas.PublicUser(
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
            consistency_score=crud_utils.calculate_consistency_score(user.workouts),
            total_workouts=len(user.workouts),
            created_at=user.created_at
        ))
    return public_users

@router.post("/request", response_model=social_schemas.FriendshipResponse)
def send_friend_request(
    request: social_schemas.FriendRequestCreate,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    if request.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot add yourself")

    return social_crud.send_friend_request(db, current_user.id, request.target_user_id)

@router.get("/friends", response_model=List[user_schemas.PublicUser])
def get_my_friends(
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    friends = social_crud.get_friends(db, current_user.id)
    
    public_friends = []
    for user in friends:
        def get_latest(arr): return arr[-1]['value'] if arr else None
        
        public_friends.append(user_schemas.PublicUser(
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
            friendship_status='accepted',
            is_friend=True,
            consistency_score=crud_utils.calculate_consistency_score(user.workouts),
            total_workouts=len(user.workouts),
            created_at=user.created_at,
            is_close_friend=getattr(user, 'is_close_friend', False)
        ))
    return public_friends

@router.get("/requests/incoming", response_model=List[user_schemas.PublicUser])
def get_incoming_requests(
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    pending_friendships = social_crud.get_pending_requests(db, current_user.id)
    requester_ids = [f.requester_id for f in pending_friendships]
    
    requesters = db.query(models.User).filter(models.User.id.in_(requester_ids)).all()
    
    public_requesters = []
    for user in requesters:
        def get_latest(arr): return arr[-1]['value'] if arr else None
        
        public_requesters.append(user_schemas.PublicUser(
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
            friendship_status='pending_received',
            is_friend=False,
            consistency_score=crud_utils.calculate_consistency_score(user.workouts),
            total_workouts=len(user.workouts),
            created_at=user.created_at
        ))
    return public_requesters

@router.get("/friends/{user_id}", response_model=List[user_schemas.PublicUser])
def get_friends_of_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if str(current_user.id) == user_id:
        return get_my_friends(current_user, db)
    
    elif social_crud.check_is_friend(db, current_user.id, user_id):
        friends = social_crud.get_friends(db, user_id)
        results = []
        for f in friends:
            u_schema = user_schemas.PublicUser.model_validate(f)
            u_schema.friendship_status = social_crud.get_friendship_status(db, current_user.id, str(f.id))
            u_schema.is_friend = (u_schema.friendship_status == 'accepted')
            u_schema.is_close_friend = False 
            results.append(u_schema)
        return results
    
    else:
        raise HTTPException(status_code=403, detail="You must be buddies to see their friends list.")

@router.put("/request/{requester_id}")
def respond_to_user_request(
    requester_id: str,
    action: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    friendship = db.query(models.Friendship).filter(
        models.Friendship.requester_id == requester_id,
        models.Friendship.addressee_id == current_user.id,
        models.Friendship.status == "pending"
    ).first()
    
    if not friendship:
        raise HTTPException(status_code=404, detail="Friend request not found")
        
    result = social_crud.respond_to_friend_request(db, current_user.id, friendship.id, action)
    if not result:
         raise HTTPException(status_code=400, detail="Failed to update request")
         
    return {"message": f"Request {action}ed"}

@router.delete("/friends/{target_user_id}")
def remove_friend(
    target_user_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    success = social_crud.remove_friend(db, current_user.id, target_user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Friendship not found or could not be removed.")
    return {"message": "Friend removed."}

@router.post("/action", response_model=dict)
def perform_social_action(
    payload: social_schemas.SocialActionCreate,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    try:
        social_crud.perform_social_action(db, current_user.id, payload.target_user_id, payload.action)
        return {"message": "Action successful"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/close-friends/{target_user_id}")
def add_close_friend(
    target_user_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    print(target_user_id)
    try:
        social_crud.toggle_close_friend(db, current_user.id, target_user_id, is_close=True)
        return {"message": "Added to Close Friends"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/close-friends/{target_user_id}")
def remove_close_friend(
    target_user_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    social_crud.toggle_close_friend(db, current_user.id, target_user_id, is_close=False)
    return {"message": "Removed from Close Friends"}
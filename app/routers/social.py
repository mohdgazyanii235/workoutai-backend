from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Annotated
from app import models
from app.database import get_db
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key
import datetime
from math import radians, cos, sin, asin, sqrt
from app.schemas import user as user_schemas
from app.schemas import social as social_schemas
from app.crud import social as social_crud
from app.crud import utils as crud_utils

router = APIRouter(
    prefix="/social",
    tags=["social"],
    dependencies=[Depends(get_api_key)]
)


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles
    return c * r

@router.get("/nearby", response_model=List[social_schemas.NearbyWorkout])
def get_nearby_opportunities(
    lat: float,
    long: float,
    radius_km: float,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Finds future public workouts from public users within a radius.
    """
    
    candidates = db.query(models.User).filter(
        models.User.profile_privacy == 'public',
        models.User.id != current_user.id,
        models.User.latitude.isnot(None),
        models.User.longitude.isnot(None)
    ).all()
    
    nearby_users = []
    for u in candidates:
        dist = haversine(long, lat, u.longitude, u.latitude)
        if dist <= radius_km:
            nearby_users.append((u, dist))
            
    if not nearby_users:
        return []
        
    nearby_user_ids = [u[0].id for u in nearby_users]
    user_dist_map = {u[0].id: u[1] for u in nearby_users}
    
    # 2. Fetch FUTURE planned workouts for these users that are PUBLIC
    now = datetime.datetime.utcnow()
    
    workouts = db.query(models.Workout).filter(
        models.Workout.user_id.in_(nearby_user_ids),
        models.Workout.status == 'planned',
        models.Workout.created_at > now,
        models.Workout.visibility == 'public' # Only public workouts in discovery
    ).order_by(models.Workout.created_at.asc()).all()
    
    results = []
    for w in workouts:
        host = next((u[0] for u in nearby_users if u[0].id == w.user_id), None)
        if not host: continue
        
        # Hydrate PublicUser schema manually or via helper
        friendship_status = social_crud.get_friendship_status(db, current_user.id, host.id)
        
        def get_latest(arr): return arr[-1]['value'] if arr else None
        
        public_host = user_schemas.PublicUser(
            id=host.id,
            first_name=host.first_name,
            last_name=host.last_name,
            city=host.city,
            country=host.country,
            bio=host.bio,
            profile_photo_url=host.profile_photo_url,
            current_bench_1rm=get_latest(host.bench_1rm),
            current_squat_1rm=get_latest(host.squat_1rm),
            current_deadlift_1rm=get_latest(host.deadlift_1rm),
            friendship_status=friendship_status,
            is_friend=(friendship_status == 'accepted'),
            consistency_score=crud_utils.calculate_consistency_score(host.workouts),
            total_workouts=len(host.workouts),
            created_at=host.created_at
        )
        
        results.append(social_schemas.NearbyWorkout(
            user=public_host,
            workout_id=w.id,
            workout_type=w.workout_type or "Workout",
            start_time=w.created_at,
            distance_km=round(user_dist_map[host.id], 1)
        ))
        
    return results

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
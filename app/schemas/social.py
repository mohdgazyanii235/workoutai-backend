from pydantic import BaseModel, ConfigDict
from datetime import datetime
from .user import PublicUser

class FriendRequestCreate(BaseModel):
    target_user_id: str

class FriendRequestAction(BaseModel):
    action: str 

class FriendshipResponse(BaseModel):
    id: str
    requester_id: str
    addressee_id: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class SocialActionCreate(BaseModel):
    target_user_id: str
    action: str

class NearbyWorkout(BaseModel):
    user: PublicUser
    workout_id: str
    workout_type: str
    start_time: datetime
    distance_km: float
    
    model_config = ConfigDict(from_attributes=True)
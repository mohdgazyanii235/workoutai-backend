from pydantic import BaseModel, ConfigDict
from datetime import datetime

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
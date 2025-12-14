from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from .user import PublicUser

class Notification(BaseModel):
    id: str
    recipient_id: str
    sender_id: Optional[str] = None
    sender: Optional[PublicUser] = None 
    type: str 
    reference_id: Optional[str] = None
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
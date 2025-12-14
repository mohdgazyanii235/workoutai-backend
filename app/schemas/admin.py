from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AdminUserSelect(BaseModel):
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class AdminNotificationCreate(BaseModel):
    target_user_ids: List[str] # List of IDs
    title: str
    message: str

class AppMetric(BaseModel):
    id: str
    user_id: str
    last_app_query: datetime
    total_api_calls: Optional[int] = 0
    open_ai_calls: Optional[int] = 0
    rubbish_voice_logs: Optional[int] = 0
    
    class Config:
        from_attributes = True

class AdminMetricResponse(BaseModel):
    metric: AppMetric
    user_email: str
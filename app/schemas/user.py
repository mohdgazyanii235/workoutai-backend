from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import date, datetime
from typing import Optional, List
from .workout import Workout # Import for type hinting if needed, though strictly it's avoided in User response often to prevent depth issues

class HistoryEntry(BaseModel):
    date: date
    value: float

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: Optional[str] = None 

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    city: Optional[str] = None
    country: Optional[str] = None

    weight: Optional[List[HistoryEntry]] = None
    height: Optional[float] = Field(None, ge=0)
    fat_percentage: Optional[List[HistoryEntry]] = None
    deadlift_1rm: Optional[List[HistoryEntry]] = None
    squat_1rm: Optional[List[HistoryEntry]] = None
    bench_1rm: Optional[List[HistoryEntry]] = None

    bio: Optional[str] = None
    profile_photo_url: Optional[str] = None

    goal_weight: Optional[float] = None
    goal_fat_percentage: Optional[float] = None
    goal_deadlift_1rm: Optional[float] = None
    goal_squat_1rm: Optional[float] = None
    goal_bench_1rm: Optional[float] = None

class User(UserBase):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    city: Optional[str] = None
    country: Optional[str] = None
    weight: List[HistoryEntry] = []
    height: Optional[float] = None
    is_onboarded: bool
    bio: Optional[str] = None
    profile_photo_url: Optional[str] = None
    fat_percentage: List[HistoryEntry] = []
    deadlift_1rm: List[HistoryEntry] = []
    squat_1rm: List[HistoryEntry] = []
    bench_1rm: List[HistoryEntry] = []
    goal_weight: Optional[float] = None
    goal_fat_percentage: Optional[float] = None
    goal_deadlift_1rm: Optional[float] = None
    goal_squat_1rm: Optional[float] = None
    goal_bench_1rm: Optional[float] = None
    created_at: datetime
    
    total_workouts: int = 0
    consistency_score: float = 0.0
    
    is_admin: bool = False
    
    class Config:
        from_attributes = True

class PublicUser(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    profile_photo_url: Optional[str] = None
    
    current_bench_1rm: Optional[float] = None
    current_squat_1rm: Optional[float] = None
    current_deadlift_1rm: Optional[float] = None
    
    consistency_score: Optional[float] = None
    total_workouts: Optional[int] = None
    is_friend: bool = False 
    friendship_status: str = "none" 
    
    nudge_count: int = 0
    spot_count: int = 0
    friend_count: int = 0
    can_nudge: bool = True
    can_spot: bool = True

    is_close_friend: bool = False

    model_config = ConfigDict(from_attributes=True)
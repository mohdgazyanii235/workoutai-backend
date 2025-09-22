# app/schemas.py
from pydantic import BaseModel, Field, EmailStr
from datetime import date, datetime
from typing import Optional, List

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
    fat_percentage: List[HistoryEntry] = []
    deadlift_1rm: List[HistoryEntry] = []
    squat_1rm: List[HistoryEntry] = []
    bench_1rm: List[HistoryEntry] = []
    goal_weight: Optional[float] = None
    goal_fat_percentage: Optional[float] = None
    goal_deadlift_1rm: Optional[float] = None
    goal_squat_1rm: Optional[float] = None
    goal_bench_1rm: Optional[float] = None
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class WorkoutLogCreate(BaseModel):
    text: str

class WorkoutBase(BaseModel):
    id: str
    notes: Optional[str] = None
    workout_type: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class Workout(WorkoutBase):
    user_id: str


# in schemas.py

class ExerciseSet(BaseModel):
    id: str
    exercise_name: str
    set_number: int
    reps: int
    weight: float
    weight_unit: str
    class Config:
        from_attributes = True

class WorkoutDetail(WorkoutBase):
    user_id: str
    sets: list[ExerciseSet] = []

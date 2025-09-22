# app/schemas.py
from pydantic import BaseModel, Field, EmailStr
from datetime import date, datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: Optional[str] = None  # email+password signup only

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    city: Optional[str] = None
    country: Optional[str] = None
    weight_kg: Optional[float] = Field(None, ge=0)
    height_cm: Optional[float] = Field(None, ge=0)

class User(UserBase):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    city: Optional[str] = None
    country: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    is_onboarded: bool  # NEW
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

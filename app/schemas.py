# app/schemas.py
from pydantic import BaseModel

# --- New Schemas for Authentication ---
class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str | None = None

class User(UserBase):
    id: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Existing Schemas ---
class WorkoutLogCreate(BaseModel):
    text: str

class Workout(BaseModel):
    id: str
    notes: str | None = None
    class Config:
        from_attributes = True
# app/schemas.py
from pydantic import BaseModel

class WorkoutLogCreate(BaseModel):
    text: str

class Workout(BaseModel):
    id: str
    notes: str | None = None

    class Config:
        orm_mode = True
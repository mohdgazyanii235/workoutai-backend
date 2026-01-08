from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

class WorkoutLogCreate(BaseModel):
    text: str
    created_at: Optional[datetime] = None

class VoiceLog(BaseModel):
    text: str
    created_at: Optional[datetime] = None

class ExerciseSet(BaseModel):
    id: str
    exercise_name: str
    set_number: int
    reps: int
    weight: float
    weight_unit: str
    
    model_config = ConfigDict(from_attributes=True)

class CardioSession(BaseModel):
    id: str
    name: str
    duration_minutes: Optional[float] = None
    distance: Optional[float] = None
    distance_unit: Optional[str] = None
    speed: Optional[float] = None
    pace: Optional[str] = None
    pace_unit: Optional[str] = None
    laps: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class WorkoutBase(BaseModel):
    id: str
    notes: Optional[str] = None
    workout_type: Optional[str] = None
    created_at: datetime
    visibility: str = "private" 
    
    model_config = ConfigDict(from_attributes=True)

class Workout(WorkoutBase):
    user_id: str

class WorkoutDetail(WorkoutBase):
    user_id: str
    sets: list[ExerciseSet] = []
    cardio_sessions: list[CardioSession] = []

class ExerciseSetUpdate(BaseModel):
    id: str | None = None
    exercise_name: str
    set_number: int
    reps: int
    weight: float
    weight_unit: str

class CardioSessionUpdate(BaseModel):
    id: str | None = None
    name: str
    duration_minutes: Optional[float] = None
    distance: Optional[float] = None
    distance_unit: Optional[str] = None
    speed: Optional[float] = None
    pace: Optional[str] = None
    pace_unit: Optional[str] = None
    laps: Optional[int] = None

class WorkoutUpdate(BaseModel):
    notes: Optional[str] = None
    workout_type: Optional[str] = None
    visibility: Optional[str] = None
    sets: Optional[List[ExerciseSetUpdate]] = None
    cardio_sessions: Optional[List[CardioSessionUpdate]] = None

class AILogResponse(BaseModel):
    comment: str

class Exercise(BaseModel):
    id: str
    exercise_name: str
    workout_types: List[str]

    model_config = ConfigDict(from_attributes=True)

class WorkoutTemplate(BaseModel):
    id: str
    template_name: str
    exercise_names: List[str]

    model_config = ConfigDict(from_attributes=True)
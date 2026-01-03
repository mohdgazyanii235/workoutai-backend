from pydantic import BaseModel, Field
from datetime import date
from typing import Optional, List, Dict, Any
from app.schemas import workout as workout_schemas

class HealthDailyCreate(BaseModel):
    date: date
    steps: Optional[int] = 0
    active_calories: Optional[float] = 0.0
    exercise_minutes: Optional[int] = 0
    resting_hr: Optional[float] = None
    avg_heart_rate: Optional[float] = None
    hrv: Optional[float] = None
    vo2_max: Optional[float] = None
    walking_hr_avg: Optional[float] = None

class ActivityDay(BaseModel):
    date: date
    active: bool

class DashboardMetrics(BaseModel):
    # Top Level "Rings"
    load_score: int 
    recovery_score: int 
    momentum_streak: int 
    
    # NEW: Historical activity map for the Dot View
    activity_history: List[ActivityDay] 

    # Vitals for the Grid
    resting_hr: Optional[float] = None
    hrv: Optional[float] = None
    vo2_max: Optional[float] = None
    
    # Context/Feedback
    message: str 

class ExerciseHistoryPoint(BaseModel):
    date: date
    one_rep_max: float 
    volume: float 

class ExerciseProgressResponse(BaseModel):
    exercise_name: str
    history: List[ExerciseHistoryPoint]

class DayViewMetrics(BaseModel):
    date: date
    health_metrics: Optional[HealthDailyCreate] = None
    workouts: List[workout_schemas.Workout] = []
    strain: float = 0.0

class ActivityHistoryResponse(BaseModel):
    # A simple list of YYYY-MM-DD strings where workouts occurred
    workout_dates: List[date]
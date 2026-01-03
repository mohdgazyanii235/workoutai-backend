from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated, List
from datetime import date
from app.database import get_db
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key
from app.schemas import analytics as analytics_schemas
from app.schemas import user as user_schemas
from app.crud import analytics as analytics_crud

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(get_api_key)]
)

@router.post("/sync")
def sync_health_data(
    data: analytics_schemas.HealthDailyCreate,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Receives daily health stats from the phone (HealthKit) and upserts them.
    """
    analytics_crud.upsert_health_daily(db, current_user.id, data)
    return {"status": "synced"}

@router.get("/day/{date_str}", response_model=analytics_schemas.DayViewMetrics)
def get_day_view(
    date_str: date, # FastAPI will automatically parse "YYYY-MM-DD" string to date
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Returns aggregated metrics and workouts for a specific day.
    """
    return analytics_crud.get_day_view_metrics(db, current_user.id, date_str)

@router.get("/dashboard", response_model=analytics_schemas.DashboardMetrics)
def get_dashboard_metrics(
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Returns the high-level metrics for the dashboard 'Pulse' UI.
    """
    return analytics_crud.get_dashboard_metrics(db, current_user.id)

@router.get("/exercise/{exercise_name}", response_model=analytics_schemas.ExerciseProgressResponse)
def get_exercise_progress(
    exercise_name: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Returns historical 1RM data for a specific exercise to plot graphs.
    """
    return analytics_crud.get_exercise_progress(db, current_user.id, exercise_name)



@router.get("/history", response_model=analytics_schemas.ActivityHistoryResponse)
def get_activity_history(
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Returns every date the user has ever logged a workout.
    Used for the all-time history calendar.
    """
    dates = analytics_crud.get_all_workout_dates(db, current_user.id)
    return {"workout_dates": dates}
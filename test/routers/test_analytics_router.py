import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import date
from app.main import app
from app import models, schemas
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key
from app.database import get_db

client = TestClient(app)
mock_user = models.User(id="u1", email="test@test.com")

app.dependency_overrides[get_current_user] = lambda: mock_user
app.dependency_overrides[get_api_key] = lambda: "key"
app.dependency_overrides[get_db] = lambda: MagicMock()

def test_sync_health_data_success():
    payload = {
        "date": "2023-01-01",
        "steps": 10000,
        "active_calories": 500.0
    }
    with patch("app.routers.analytics.analytics_crud.upsert_health_daily") as mock_upsert:
        response = client.post("/analytics/sync", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "synced"
        mock_upsert.assert_called_once()

def test_sync_health_data_validation_error():
    # Missing required 'date'
    payload = {"steps": 10000} 
    response = client.post("/analytics/sync", json=payload)
    assert response.status_code == 422

def test_get_day_view_success():
    target_date = date(2023, 1, 1)
    mock_metrics = schemas.analytics.DayViewMetrics(
        date=target_date,
        strain=5.0,
        health_metrics=None,
        workouts=[]
    )
    
    with patch("app.routers.analytics.analytics_crud.get_day_view_metrics", return_value=mock_metrics):
        response = client.get("/analytics/day/2023-01-01")
        assert response.status_code == 200
        assert response.json()["strain"] == 5.0
        assert response.json()["date"] == "2023-01-01"

def test_get_dashboard_metrics_success():
    mock_dash = schemas.analytics.DashboardMetrics(
        load_score=80,
        recovery_score=90,
        momentum_streak=5,
        activity_history=[],
        message="Keep it up"
    )
    
    with patch("app.routers.analytics.analytics_crud.get_dashboard_metrics", return_value=mock_dash):
        response = client.get("/analytics/dashboard")
        assert response.status_code == 200
        assert response.json()["load_score"] == 80

def test_get_exercise_progress_success():
    mock_prog = schemas.analytics.ExerciseProgressResponse(
        exercise_name="Bench",
        history=[
            schemas.analytics.ExerciseHistoryPoint(date=date(2023,1,1), one_rep_max=100.0, volume=0)
        ]
    )
    
    with patch("app.routers.analytics.analytics_crud.get_exercise_progress", return_value=mock_prog):
        response = client.get("/analytics/exercise/Bench")
        assert response.status_code == 200
        assert response.json()["exercise_name"] == "Bench"
        assert len(response.json()["history"]) == 1

def test_get_activity_history_success():
    mock_dates = [date(2023, 1, 1), date(2023, 1, 2)]
    
    with patch("app.routers.analytics.analytics_crud.get_all_workout_dates", return_value=mock_dates):
        response = client.get("/analytics/history")
        assert response.status_code == 200
        data = response.json()
        assert "workout_dates" in data
        assert len(data["workout_dates"]) == 2
        assert data["workout_dates"][0] == "2023-01-01"
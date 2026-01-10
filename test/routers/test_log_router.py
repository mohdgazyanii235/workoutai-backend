import pytest
from fastapi.testclient import TestClient
from fastapi.exceptions import ResponseValidationError
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, date
from app.main import app
from app import models, schemas
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key
from app.database import get_db
from app.services.ai_service import InvalidWorkoutException
from types import SimpleNamespace

client = TestClient(app)
mock_user = models.User(id="u1", email="test@test.com")

app.dependency_overrides[get_current_user] = lambda: mock_user
app.dependency_overrides[get_api_key] = lambda: "key"
app.dependency_overrides[get_db] = lambda: MagicMock()

# --- Helpers ---
def create_mock_voice_log(**kwargs):
    """
    Helper to create a mock object that mimics the structure returned by ai_service.
    We use SimpleNamespace to allow attribute access (log.sets, log.cardio) which 
    the router expects, avoiding Pydantic schema validation issues during mocking.
    """
    defaults = {
        "text": "test input",
        "cardio": [],
        "sets": [],
        "note": "",
        "workout_type": "",
        "visibility": "private",
        "comment": "AI comment",
        "updated_weight": None,
        "updated_weight_unit": "",
        "updated_bench_1rm": None,
        "updated_bench_1rm_unit": "",
        "updated_squat_1rm": None,
        "updated_squat_1rm_unit": "",
        "updated_deadlift_1rm": None,
        "updated_deadlift_1rm_unit": "",
        "updated_fat_percentage": None,
        "scheduled_date": None # Added default for new feature
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)

# --- Tests ---

def test_voice_log_pyramid_sets():
    """
    Test logging a pyramid set: "12 reps 50kg, 10 reps 60kg, 8 reps 70kg".
    Should result in multiple ExerciseSet objects in the VoiceLog.
    """
    input_text = "I did bench press 12 reps 50kg, 10 reps 60kg, 8 reps 70kg"
    
    # We use SimpleNamespace for nested objects too to ensure attribute access works
    mock_sets = [
        SimpleNamespace(id="s1", exercise_name="Bench Press", reps=12, weight=50, weight_unit="kg", sets=1),
        SimpleNamespace(id="s2", exercise_name="Bench Press", reps=10, weight=60, weight_unit="kg", sets=2),
        SimpleNamespace(id="s3", exercise_name="Bench Press", reps=8, weight=70, weight_unit="kg", sets=3)
    ]
    
    mock_response = create_mock_voice_log(
        text=input_text,
        sets=mock_sets,
        workout_type="Chest",
        comment="Great pyramid set!"
    )

    with patch("app.routers.log.ai_service.structured_log_text", return_value=mock_response):
        with patch("app.routers.log.admin_crud.log_open_ai_query"):
            with patch("app.routers.log.workout_crud.manage_voice_log", return_value="Great pyramid set!") as mock_manage:
                
                response = client.post("/log/voice", json={"text": input_text})
                
                assert response.status_code == 200
                assert response.json()["comment"] == "Great pyramid set!"
                
                # Verify manage_voice_log was called with the correct structure
                args, _ = mock_manage.call_args
                called_log = args[1]
                assert len(called_log.sets) == 3
                assert called_log.sets[0].weight == 50
                assert called_log.sets[2].weight == 70

def test_voice_log_straight_sets():
    """
    Test logging straight sets: "3 sets of 10 at 100kg".
    Should result in a single ExerciseSet object with sets=3 (as per AI service prompt rules).
    """
    input_text = "I did 3 sets of 10 squats at 100kg"
    
    mock_sets = [
        SimpleNamespace(id="s1", exercise_name="Squat", reps=10, weight=100, weight_unit="kg", sets=3)
    ]
    
    mock_response = create_mock_voice_log(
        text=input_text,
        sets=mock_sets,
        workout_type="Legs",
        comment="Solid squats."
    )

    with patch("app.routers.log.ai_service.structured_log_text", return_value=mock_response):
        with patch("app.routers.log.admin_crud.log_open_ai_query"):
            with patch("app.routers.log.workout_crud.manage_voice_log", return_value="Solid squats.") as mock_manage:
                
                response = client.post("/log/voice", json={"text": input_text})
                
                assert response.status_code == 200
                
                args, _ = mock_manage.call_args
                called_log = args[1]
                assert len(called_log.sets) == 1
                assert called_log.sets[0].sets == 3
                assert called_log.sets[0].reps == 10

def test_voice_log_mixed_workout_cardio_and_weights():
    """
    Test a mixed workout: "Ran 2 miles then did 3 sets of bench press".
    Should contain both cardio and sets.
    """
    input_text = "Ran 2 miles then did 3 sets of bench press"
    
    mock_cardio = [
        SimpleNamespace(id="c1", exercise_name="Running", name="Running", distance=2.0, distance_unit="miles", duration_minutes=20, speed=None, pace=None, pace_unit=None, laps=None)
    ]
    mock_sets = [
        SimpleNamespace(id="s1", exercise_name="Bench Press", reps=10, weight=80, weight_unit="kg", sets=3)
    ]
    
    mock_response = create_mock_voice_log(
        text=input_text,
        cardio=mock_cardio,
        sets=mock_sets,
        workout_type="Hybrid",
        comment="Good mix!"
    )

    with patch("app.routers.log.ai_service.structured_log_text", return_value=mock_response):
        with patch("app.routers.log.admin_crud.log_open_ai_query"):
            with patch("app.routers.log.workout_crud.manage_voice_log", return_value="Good mix!") as mock_manage:
                
                response = client.post("/log/voice", json={"text": input_text})
                
                assert response.status_code == 200
                
                args, _ = mock_manage.call_args
                called_log = args[1]
                assert len(called_log.cardio) == 1
                assert called_log.cardio[0].name == "Running"
                assert len(called_log.sets) == 1
                assert called_log.sets[0].exercise_name == "Bench Press"

def test_voice_log_metrics_updates():
    """
    Test updating body metrics: Weight, Fat%, 1RM.
    """
    input_text = "My new weight is 75kg, body fat 15%, bench 1rm is 100kg"
    
    mock_response = create_mock_voice_log(
        text=input_text,
        updated_weight=75.0,
        updated_weight_unit="kg",
        updated_fat_percentage=15.0,
        updated_bench_1rm=100.0,
        updated_bench_1rm_unit="kg",
        comment="Metrics updated."
    )

    with patch("app.routers.log.ai_service.structured_log_text", return_value=mock_response):
        with patch("app.routers.log.admin_crud.log_open_ai_query"):
            with patch("app.routers.log.workout_crud.manage_voice_log", return_value="Metrics updated.") as mock_manage:
                
                response = client.post("/log/voice", json={"text": input_text})
                
                assert response.status_code == 200
                
                args, _ = mock_manage.call_args
                called_log = args[1]
                assert called_log.updated_weight == 75.0
                assert called_log.updated_fat_percentage == 15.0
                assert called_log.updated_bench_1rm == 100.0
                # Ensure no workout data created if not present
                assert called_log.sets == []
                assert called_log.cardio == []

def test_voice_log_scheduled_workout():
    """
    Test that the router correctly handles a scheduled date from the AI.
    """
    input_text = "Schedule chest for next Friday"
    future_date = date(2023, 12, 25)
    
    mock_response = create_mock_voice_log(
        text=input_text,
        scheduled_date=future_date,
        workout_type="Chest",
        comment="Scheduled for Christmas"
    )
    
    with patch("app.routers.log.ai_service.structured_log_text", return_value=mock_response):
        with patch("app.routers.log.admin_crud.log_open_ai_query"):
            with patch("app.routers.log.workout_crud.manage_voice_log", return_value="Scheduled.") as mock_manage:
                
                response = client.post("/log/voice", json={"text": input_text})
                assert response.status_code == 200
                
                # Check that the scheduled_date was passed down
                args, _ = mock_manage.call_args
                called_log = args[1]
                assert called_log.scheduled_date == future_date

def test_voice_log_conversational():
    """
    Test non-workout input: "Hi how is the weather".
    Should return a comment but (crucially) NOT create a workout.
    """
    input_text = "Hi how is the weather"
    
    # AI recognizes it's not a workout, returns empty fields but a comment
    mock_response = create_mock_voice_log(
        text=input_text,
        comment="I'm a fitness AI, let's talk workouts!",
        sets=[],
        cardio=[]
    )

    with patch("app.routers.log.ai_service.structured_log_text", return_value=mock_response):
        with patch("app.routers.log.admin_crud.log_open_ai_query"):
            with patch("app.routers.log.workout_crud.manage_voice_log", return_value="I'm a fitness AI, let's talk workouts!"):
                response = client.post("/log/voice", json={"text": input_text})
                
                assert response.status_code == 200
                assert response.json()["comment"] == "I'm a fitness AI, let's talk workouts!"

def test_voice_log_invalid_exception():
    """Test AI service raising InvalidWorkoutException explicitly."""
    with patch("app.routers.log.ai_service.structured_log_text", side_effect=InvalidWorkoutException("Invalid input")):
        response = client.post("/log/voice", json={"text": "garbage"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid input"

def test_voice_log_empty_response():
    """Test where AI returns None (fails to parse)."""
    with patch("app.routers.log.ai_service.structured_log_text", return_value=None):
        # We expect a ResponseValidationError because the code returns a string "u1" 
        # but the schema expects {comment: str}.
        with pytest.raises(ResponseValidationError):
            client.post("/log/voice", json={"text": "..."})
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from app.main import app
from app import models, schemas
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key
from app.database import get_db

# Helper to create a compliant mock user
def create_mock_user(id="test-user-id", email="test@example.com", **kwargs):
    defaults = {
        "id": id,
        "email": email,
        "is_admin": False,
        "is_onboarded": True,
        "created_at": datetime.now(timezone.utc),
        "weight": [], "fat_percentage": [], "deadlift_1rm": [],
        "squat_1rm": [], "bench_1rm": [], "workouts": []
    }
    defaults.update(kwargs)
    return models.User(**defaults)

mock_db_session = MagicMock()

@pytest.fixture(autouse=True)
def setup_dependency_overrides():
    mock_user = create_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_api_key] = lambda: "valid-api-key"
    app.dependency_overrides[get_db] = lambda: mock_db_session
    yield
    app.dependency_overrides = {}
    mock_db_session.reset_mock()

client = TestClient(app)

# --- Tests ---

def test_get_workouts_success():
    """Test retrieving a list of workouts for the current user."""
    mock_workout = models.Workout(
        id="w1", 
        user_id="test-user-id", 
        created_at=datetime.now(timezone.utc),
        visibility="private",
        notes="Test note",
        workout_type="Strength"
    )
    
    # We must patch get_db in the module it is imported into, OR configure the mock_db_session we injected
    # Configuring the injected mock_db_session is cleaner and matches the override strategy.
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_workout]
    
    response = client.get("/workouts/")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "w1"

def test_get_workout_detail_success():
    """Test retrieving a specific workout detail."""
    mock_workout = models.Workout(
        id="w1", 
        user_id="test-user-id", 
        created_at=datetime.now(timezone.utc),
        visibility="private",
        notes="Test note",
        workout_type="Strength",
        sets=[],
        cardio_sessions=[]
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_workout

    response = client.get("/workouts/w1")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "w1"
    assert "sets" in data
    assert "cardio_sessions" in data

def test_get_workout_not_found():
    """Test 404 when workout does not exist."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client.get("/workouts/non-existent")
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Workout not found"

def test_delete_workout_success():
    """Test successful deletion."""
    mock_workout = models.Workout(
        id="w1", 
        user_id="test-user-id",
        created_at=datetime.now(timezone.utc),
        visibility="private",
        notes="Test",
        workout_type="Strength"
    )
    
    with patch("app.routers.workouts.workout_crud.delete_workout", return_value=mock_workout):
        response = client.delete("/workouts/w1")
        assert response.status_code == 200
        assert response.json()["id"] == "w1"

def test_delete_workout_not_found():
    """Test deletion of non-existent workout."""
    with patch("app.routers.workouts.workout_crud.delete_workout", return_value=None):
        response = client.delete("/workouts/w1")
        assert response.status_code == 404
        assert response.json()["detail"] == "Workout not found"

def test_update_workout_success():
    """Test successful workout update."""
    payload = {"notes": "Updated notes", "visibility": "public"}
    
    mock_response = models.Workout(
        id="w1", 
        user_id="test-user-id", 
        notes="Updated notes", 
        visibility="public",
        workout_type="Strength",
        created_at=datetime.now(timezone.utc),
        sets=[],             
        cardio_sessions=[]   
    )
    
    with patch("app.routers.workouts.workout_crud.update_workout", return_value=mock_response):
        response = client.put("/workouts/w1", json=payload)
        assert response.status_code == 200
        assert response.json()["notes"] == "Updated notes"

def test_update_workout_not_found():
    """Test update returns 404 if CRUD returns None."""
    payload = {"notes": "Updated notes"}
    
    with patch("app.routers.workouts.workout_crud.update_workout", return_value=None):
        response = client.put("/workouts/w1", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "Workout not found or user not authorized"

def test_update_workout_server_error():
    """Test handling of unexpected errors during update."""
    payload = {"notes": "Updated notes"}
    
    with patch("app.routers.workouts.workout_crud.update_workout", side_effect=Exception("DB Error")):
        response = client.put("/workouts/w1", json=payload)
        assert response.status_code == 500
        assert "Failed to update workout" in response.json()["detail"]

def test_create_workout_manual_success():
    """Test manual creation."""
    payload = {
        "notes": "New workout",
        "workout_type": "Strength",
        "sets": []
    }
    mock_created = models.Workout(
        id="new-w", 
        user_id="test-user-id", 
        notes="New workout",
        workout_type="Strength",
        visibility="private",
        created_at=datetime.now(timezone.utc),
        sets=[],
        cardio_sessions=[]
    )
    
    with patch("app.routers.workouts.workout_crud.create_manual_workout", return_value=mock_created):
        response = client.post("/workouts", json=payload)
        assert response.status_code == 200
        assert response.json()["id"] == "new-w"

def test_create_workout_manual_error():
    """Test manual creation error handling."""
    payload = {"notes": "New workout"}
    
    with patch("app.routers.workouts.workout_crud.create_manual_workout", side_effect=Exception("Boom")):
        response = client.post("/workouts", json=payload)
        assert response.status_code == 500
        assert "Failed to create workout" in response.json()["detail"]

def test_get_user_public_workouts_accepted_friend():
    """Test viewing a friend's workouts."""
    target_user_id = "target-u1"
    
    with patch("app.routers.workouts.social_crud.get_friendship_status", return_value="accepted"):
        mock_workouts = [
            models.Workout(
                id="w1", 
                user_id=target_user_id, 
                created_at=datetime.now(timezone.utc),
                visibility="public",
                notes="Note",
                workout_type="Strength"
            )
        ]
        with patch("app.routers.workouts.workout_crud.get_visible_workouts_for_user", return_value=mock_workouts):
            
            response = client.get(f"/workouts/user/{target_user_id}")
            
            assert response.status_code == 200
            assert len(response.json()) == 1

def test_get_user_public_workouts_not_friend():
    """Test getting workouts for non-friend returns empty list."""
    target_user_id = "target-u1"
    
    with patch("app.routers.workouts.social_crud.get_friendship_status", return_value="none"):
        response = client.get(f"/workouts/user/{target_user_id}")
        assert response.status_code == 200
        assert response.json() == []

def test_get_public_workout_detail_owner():
    """Test owner can always see their own workout via the public endpoint."""
    workout_id = "w1"
    mock_workout = models.Workout(
        id=workout_id, 
        user_id="test-user-id", # Same as current user
        created_at=datetime.now(timezone.utc),
        visibility="private",
        notes="My notes",
        workout_type="Strength",
        sets=[],
        cardio_sessions=[]
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_workout
    
    response = client.get(f"/workouts/public/{workout_id}")
    assert response.status_code == 200
    assert response.json()["id"] == workout_id

def test_get_public_workout_detail_not_friend():
    """Test 403 if not friends."""
    workout_id = "w1"
    owner_id = "other-user"
    mock_workout = models.Workout(id=workout_id, user_id=owner_id)
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_workout
    
    with patch("app.routers.workouts.social_crud.get_friendship_status", return_value="none"):
        response = client.get(f"/workouts/public/{workout_id}")
        assert response.status_code == 403
        assert response.json()["detail"] == "You are not buddies with the workout owner."

def test_get_public_workout_detail_close_friend_success():
    """Test close friend can see close_friends visibility."""
    workout_id = "w1"
    owner_id = "other-user"
    mock_workout = models.Workout(
        id=workout_id, 
        user_id=owner_id, 
        visibility="close_friends",
        created_at=datetime.now(timezone.utc),
        notes="Secret notes",
        workout_type="Strength",
        sets=[],
        cardio_sessions=[]
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_workout
    
    with patch("app.routers.workouts.social_crud.get_friendship_status", return_value="accepted"):
        with patch("app.routers.workouts.social_crud.check_is_close_friend", return_value=True):
            
            response = client.get(f"/workouts/public/{workout_id}")
            assert response.status_code == 200
            assert response.json()["notes"] is None 

def test_get_public_workout_detail_close_friend_fail():
    """Test friend (but not close friend) cannot see close_friends visibility."""
    workout_id = "w1"
    owner_id = "other-user"
    mock_workout = models.Workout(
        id=workout_id, 
        user_id=owner_id, 
        visibility="close_friends",
        created_at=datetime.now(timezone.utc),
        sets=[],
        cardio_sessions=[]
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_workout
    
    with patch("app.routers.workouts.social_crud.get_friendship_status", return_value="accepted"):
        with patch("app.routers.workouts.social_crud.check_is_close_friend", return_value=False):
            
            response = client.get(f"/workouts/public/{workout_id}")
            assert response.status_code == 403
            assert response.json()["detail"] == "This workout is restricted to Close Friends."

def test_get_public_workout_detail_private():
    """Test 404/403 for private visibility even if friends."""
    workout_id = "w1"
    owner_id = "other-user"
    mock_workout = models.Workout(id=workout_id, user_id=owner_id, visibility="private")
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_workout
    
    with patch("app.routers.workouts.social_crud.get_friendship_status", return_value="accepted"):
        response = client.get(f"/workouts/public/{workout_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Workout is private"
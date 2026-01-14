import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
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
    # Ensure consistency: Use "u1" as the standard test user ID
    mock_user = create_mock_user(id="u1")
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
        user_id="u1", # Matched to fixture
        created_at=datetime.now(timezone.utc),
        visibility="private",
        notes="Test note",
        workout_type="Strength",
        status="completed"
    )
    
    # We must patch get_db in the module it is imported into, OR configure the mock_db_session we injected
    # Configuring the injected mock_db_session is cleaner and matches the override strategy.
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_workout]
    
    response = client.get("/workouts/")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "w1"
    assert data[0]["status"] == "completed"

def test_get_workout_detail_success():
    """Test retrieving a specific workout detail."""
    mock_workout = models.Workout(
        id="w1", 
        user_id="u1", 
        created_at=datetime.now(timezone.utc),
        visibility="private",
        notes="Test note",
        workout_type="Strength",
        status="completed",
        sets=[],
        cardio_sessions=[]
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_workout

    response = client.get("/workouts/w1")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "w1"
    assert data["status"] == "completed"
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
        user_id="u1", 
        created_at=datetime.now(timezone.utc),
        visibility="private",
        notes="Test",
        workout_type="Strength",
        status="completed"
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
        user_id="u1", 
        notes="Updated notes", 
        visibility="public",
        workout_type="Strength",
        created_at=datetime.now(timezone.utc),
        status="completed",
        sets=[],             
        cardio_sessions=[]   
    )
    
    with patch("app.routers.workouts.workout_crud.update_workout", return_value=mock_response):
        response = client.put("/workouts/w1", json=payload)
        assert response.status_code == 200
        assert response.json()["notes"] == "Updated notes"
        assert response.json()["status"] == "completed"

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
        user_id="u1", 
        notes="New workout",
        workout_type="Strength",
        visibility="private",
        created_at=datetime.now(timezone.utc),
        status="completed",
        sets=[],
        cardio_sessions=[]
    )
    
    with patch("app.routers.workouts.workout_crud.create_manual_workout", return_value=mock_created):
        response = client.post("/workouts", json=payload)
        assert response.status_code == 200
        assert response.json()["id"] == "new-w"
        assert response.json()["status"] == "completed"

def test_create_workout_manual_scheduled():
    """Test manually creating a scheduled workout."""
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    payload = {
        "notes": "Planned",
        "created_at": future,
        "workout_type": "Strength",
        "sets": []
    }
    
    # Mock return value should reflect the planned status
    mock_created = models.Workout(
        id="planned-w", 
        user_id="u1", 
        notes="Planned",
        workout_type="Strength",
        visibility="private",
        created_at=datetime.fromisoformat(future),
        status="planned",
        sets=[],
        cardio_sessions=[]
    )
    
    with patch("app.routers.workouts.workout_crud.create_manual_workout", return_value=mock_created):
        response = client.post("/workouts", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "planned"

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
                workout_type="Strength",
                status="completed"
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
        user_id="u1", # Same as current user (updated from test-user-id)
        created_at=datetime.now(timezone.utc),
        visibility="private",
        notes="My notes",
        workout_type="Strength",
        status="completed",
        sets=[],
        cardio_sessions=[]
    )
    
    # We need to make sure the mocked workout is returned for the specific query
    # The endpoint calls: db.query(models.Workout).filter(models.Workout.id == workout_id).first()
    # But get_workout_detail also checks if user is friend if not owner.
    # Here owner is viewing.
    
    # Reset mock to clear previous configurations if necessary
    mock_db_session.reset_mock()
    
    # Configure the mock chain for: db.query(models.Workout).filter(models.Workout.id == workout_id).first()
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_workout
    
    # The authenticated user is "u1" (from fixture)
    # The workout owner is "u1"
    # So it should return the workout directly.
    
    response = client.get(f"/workouts/public/{workout_id}")
    
    # Debugging print if test fails
    if response.status_code != 200:
        print(response.json())
        
    assert response.status_code == 200
    assert response.json()["id"] == workout_id

def test_get_public_workout_detail_not_friend():
    """Test 403 if not friends."""
    workout_id = "w1"
    owner_id = "other-user"
    mock_workout = models.Workout(id=workout_id, user_id=owner_id, status="completed")
    
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
        status="completed",
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
        cardio_sessions=[],
        status="completed"
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
    mock_workout = models.Workout(id=workout_id, user_id=owner_id, visibility="private", status="completed")
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_workout
    
    with patch("app.routers.workouts.social_crud.get_friendship_status", return_value="accepted"):
        response = client.get(f"/workouts/public/{workout_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Workout is private"


def test_router_request_join_success():
    """Test POST /join triggers crud function."""
    with patch("app.routers.workouts.workout_crud.request_join_workout") as mock_crud:
        mock_crud.return_value = {"message": "Request sent successfully"}
        
        response = client.post("/workouts/w1/join")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Request sent successfully"
        mock_crud.assert_called_once()
        # Verify arguments passed to crud
        args = mock_crud.call_args
        assert args[0][1] == "w1" # workout_id
        assert args[0][2] == "u1" # requester_id (current_user)

def test_router_request_join_error():
    """Test POST /join handles CRUD error dicts."""
    with patch("app.routers.workouts.workout_crud.request_join_workout") as mock_crud:
        mock_crud.return_value = {"error": "Private workout", "code": 403}
        
        response = client.post("/workouts/w1/join")
        
        assert response.status_code == 403
        assert response.json()["detail"] == "Private workout"

def test_router_respond_join_success():
    """Test PUT /requests/{id} triggers crud function."""
    payload = {"action": "accept"}
    
    with patch("app.routers.workouts.workout_crud.respond_join_request") as mock_crud:
        mock_crud.return_value = {"message": "Accepted"}
        
        response = client.put("/workouts/w1/requests/u2", json=payload)
        
        assert response.status_code == 200
        assert response.json()["message"] == "Accepted"
        
        # Verify crud args
        args = mock_crud.call_args
        # respond_join_request(db, workout_id, host_id, requester_id, action)
        assert args[0][1] == "w1" # workout_id
        assert args[0][2] == "u1" # host_id (current_user)
        assert args[0][3] == "u2" # requester_id
        assert args[0][4] == "accept" # action

def test_router_respond_join_invalid_action():
    """Test schema validation for action."""
    # Although schema validation happens at Pydantic level, good to ensure
    # crud returns errors handled by router
    with patch("app.routers.workouts.workout_crud.respond_join_request") as mock_crud:
        mock_crud.return_value = {"error": "Invalid action", "code": 400}
        
        response = client.put("/workouts/w1/requests/u2", json={"action": "bad_action"})
        
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid action"

def test_router_leave_workout():
    """Test DELETE /members triggers crud function."""
    with patch("app.routers.workouts.workout_crud.leave_workout") as mock_crud:
        mock_crud.return_value = {"message": "Left"}
        
        response = client.delete("/workouts/w1/members")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Left"
        
        args = mock_crud.call_args
        assert args[0][1] == "w1" # workout_id
        assert args[0][2] == "u1" # user_id
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
def create_mock_user(id, email="test@test.com", **kwargs):
    defaults = {
        "id": id,
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "city": "City",
        "country": "Country",
        "bio": "Bio",
        "profile_photo_url": None,
        "created_at": datetime.now(timezone.utc),
        "nudge_count": 0,
        "spot_count": 0,
        "is_admin": False,
        "bench_1rm": [],
        "squat_1rm": [],
        "deadlift_1rm": [],
        "workouts": []
    }
    defaults.update(kwargs)
    return models.User(**defaults)

# Define mock_db_session globally for the module so tests can configure it
mock_db_session = MagicMock()

@pytest.fixture(autouse=True)
def setup_dependency_overrides():
    """
    Fixture to setup and TEARDOWN dependency overrides.
    This ensures that overrides from this file don't leak to others,
    and overrides from others don't affect this one (if they clean up properly).
    """
    # Create a fresh mock user for this module's tests
    mock_user = create_mock_user(id="u1")
    
    # Set overrides
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_api_key] = lambda: "key"
    app.dependency_overrides[get_db] = lambda: mock_db_session
    
    yield
    
    # Clear overrides after tests in this module finish
    app.dependency_overrides = {}
    
    # Reset the mock DB for the next test
    mock_db_session.reset_mock()

client = TestClient(app)

# --- Search ---

def test_search_users_short_query():
    response = client.get("/social/search?query=ab")
    assert response.status_code == 200
    assert response.json() == []

def test_search_users_success():
    mock_found = create_mock_user(id="u2", first_name="Bob")
    
    with patch("app.routers.social.social_crud.search_users", return_value=[mock_found]):
        with patch("app.routers.social.social_crud.get_friendship_status", return_value="none"):
            with patch("app.routers.social.crud_utils.calculate_consistency_score", return_value=50.0):
                response = client.get("/social/search?query=Bob")
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["first_name"] == "Bob"

# --- Friend Requests ---

def test_send_friend_request_success():
    payload = {"target_user_id": "u2"}
    mock_resp = models.Friendship(id="f1", requester_id="u1", addressee_id="u2", status="pending", created_at=datetime.now(timezone.utc))
    
    with patch("app.routers.social.social_crud.send_friend_request", return_value=mock_resp):
        response = client.post("/social/request", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

def test_send_friend_request_self_add():
    """
    Test that adding oneself returns 400.
    Relies on get_current_user returning a user with id="u1".
    """
    payload = {"target_user_id": "u1"} # Same as current user (u1)
    
    # We don't need to patch send_friend_request because we expect it to fail BEFORE calling that.
    # However, if the test fails (logic error), it might call it.
    
    response = client.post("/social/request", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot add yourself"

def test_respond_to_request_success():
    # Setup the mock DB to return the friendship when queried
    mock_friendship = models.Friendship(id="f1", requester_id="u2", addressee_id="u1", status="pending")
    # We must configure the specific query chain that the router uses:
    # friendship = db.query(models.Friendship).filter(...).first()
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_friendship

    with patch("app.routers.social.social_crud.respond_to_friend_request", return_value=True):
        response = client.put("/social/request/u2?action=accept")
        assert response.status_code == 200
        assert "accepted" in response.json()["message"]

def test_respond_to_request_not_found():
    # Setup the mock DB to return None
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client.put("/social/request/u2?action=accept")
    assert response.status_code == 404
    assert response.json()["detail"] == "Friend request not found"

# --- Friends List ---

def test_get_my_friends():
    mock_friend = create_mock_user(id="u2", first_name="Pal")
    # Mock is_close_friend attribute which might be attached dynamically
    mock_friend.is_close_friend = True 
    
    with patch("app.routers.social.social_crud.get_friends", return_value=[mock_friend]):
        with patch("app.routers.social.crud_utils.calculate_consistency_score", return_value=100.0):
            response = client.get("/social/friends")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["is_close_friend"] is True

def test_get_friends_of_user_allowed():
    # Viewing u2's friends (we are u1)
    target_id = "u2"
    mock_friend_of_u2 = create_mock_user(id="u3", first_name="Third")
    
    with patch("app.routers.social.social_crud.check_is_friend", return_value=True): # We are friends with u2
        with patch("app.routers.social.social_crud.get_friends", return_value=[mock_friend_of_u2]):
            with patch("app.routers.social.social_crud.get_friendship_status", return_value="none"): # status with u3
                response = client.get(f"/social/friends/{target_id}")
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["id"] == "u3"

def test_get_friends_of_user_forbidden():
    target_id = "u2"
    with patch("app.routers.social.social_crud.check_is_friend", return_value=False):
        response = client.get(f"/social/friends/{target_id}")
        assert response.status_code == 403

# --- Actions ---

def test_perform_social_action_success():
    payload = {"target_user_id": "u2", "action": "nudge"}
    with patch("app.routers.social.social_crud.perform_social_action", return_value=True):
        response = client.post("/social/action", json=payload)
        assert response.status_code == 200

def test_perform_social_action_limit_reached():
    payload = {"target_user_id": "u2", "action": "nudge"}
    with patch("app.routers.social.social_crud.perform_social_action", side_effect=ValueError("Limit reached")):
        response = client.post("/social/action", json=payload)
        assert response.status_code == 400
        assert "Limit reached" in response.json()["detail"]

# --- Close Friends ---

def test_add_close_friend_success():
    with patch("app.routers.social.social_crud.toggle_close_friend"):
        response = client.post("/social/close-friends/u2")
        assert response.status_code == 200

def test_add_close_friend_not_buddies():
    with patch("app.routers.social.social_crud.toggle_close_friend", side_effect=ValueError("Must be buddies")):
        response = client.post("/social/close-friends/u2")
        assert response.status_code == 400
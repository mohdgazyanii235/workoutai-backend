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
def create_mock_user(id="u1", email="test@test.com", **kwargs):
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
        "is_onboarded": False,
        "is_admin": False,
        "nudge_count": 0,
        "spot_count": 0,
        "weight": [],
        "height": 180.0,
        "fat_percentage": [],
        "deadlift_1rm": [],
        "squat_1rm": [],
        "bench_1rm": [],
        "workouts": [],
        "goal_weight": None,
        "goal_fat_percentage": None,
        "goal_deadlift_1rm": None,
        "goal_squat_1rm": None,
        "goal_bench_1rm": None
    }
    defaults.update(kwargs)
    return models.User(**defaults)

mock_db_session = MagicMock()

@pytest.fixture(autouse=True)
def setup_dependency_overrides():
    mock_user = create_mock_user(id="u1")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_api_key] = lambda: "key"
    app.dependency_overrides[get_db] = lambda: mock_db_session
    yield
    app.dependency_overrides = {}
    mock_db_session.reset_mock()

client = TestClient(app)

def test_get_me_success():
    # Ensure get_user returns the fully populated mock
    # The fixture sets `get_current_user`, but the router logic calls `user_crud.get_user(db, id=current_user.id)`
    # So we must mock `user_crud.get_user` to return our mock user object as well.
    mock_user = create_mock_user(id="u1")
    
    with patch("app.routers.users.user_crud.get_user", return_value=mock_user):
        with patch("app.routers.users.crud_utils.calculate_consistency_score", return_value=95.0):
            response = client.get("/users/me")
            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "test@test.com"
            assert data["consistency_score"] == 95.0
            assert data["is_onboarded"] is False

def test_get_me_not_found():
    # Simulating DB fail to find user despite auth (edge case)
    with patch("app.routers.users.user_crud.get_user", return_value=None):
        response = client.get("/users/me")
        assert response.status_code == 404

def test_update_me_success():
    payload = {"first_name": "Updated"}
    # The updated user must also be fully compliant
    mock_updated = create_mock_user(id="u1", email="test@test.com", first_name="Updated")
    
    with patch("app.routers.users.user_crud.update_user_profile", return_value=mock_updated):
        response = client.put("/users/me", json=payload)
        assert response.status_code == 200
        assert response.json()["first_name"] == "Updated"
        assert response.json()["is_onboarded"] is False

def test_get_public_profile_success():
    target_id = "u2"
    mock_target = create_mock_user(id="u2", first_name="Target")
    
    with patch("app.routers.users.user_crud.get_user", return_value=mock_target):
        with patch("app.routers.users.social_crud.get_friendship_status", return_value="accepted"):
            with patch("app.routers.users.social_crud.get_weekly_interaction_count", return_value=0):
                with patch("app.routers.users.social_crud.get_friend_count", return_value=5):
                    
                    response = client.get(f"/users/{target_id}/public")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["is_friend"] is True
                    assert data["can_nudge"] is True

def test_get_public_profile_not_found():
    with patch("app.routers.users.user_crud.get_user", return_value=None):
        response = client.get("/users/bad_id/public")
        assert response.status_code == 404
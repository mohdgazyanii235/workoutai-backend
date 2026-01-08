import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from app.main import app
from app import models, schemas
from app.security.security import get_api_key
from app.database import get_db

client = TestClient(app)

# Common mock user with all fields required by User schema
def create_mock_user(id="u1", email="test@test.com"):
    return models.User(
        id=id,
        email=email,
        is_admin=False,
        is_onboarded=False,
        created_at=datetime.now(timezone.utc),
        # Initialize lists to satisfy Pydantic list types
        weight=[],
        fat_percentage=[],
        deadlift_1rm=[],
        squat_1rm=[],
        bench_1rm=[],
        workouts=[] 
    )

app.dependency_overrides[get_api_key] = lambda: "key"
app.dependency_overrides[get_db] = lambda: MagicMock()

def test_signup_success():
    payload = {"email": "new@test.com", "password": "pass"}
    mock_user = create_mock_user(id="u1", email="new@test.com")
    
    # Mock user check (returns None -> user doesn't exist)
    with patch("app.routers.auth.user_crud.get_user_by_email", return_value=None):
        with patch("app.routers.auth.user_crud.create_user", return_value=mock_user):
            response = client.post("/auth/signup", json=payload)
            assert response.status_code == 200
            assert response.json()["email"] == "new@test.com"

def test_signup_email_exists():
    payload = {"email": "exists@test.com", "password": "pass"}
    mock_user = create_mock_user(id="u1", email="exists@test.com")
    
    with patch("app.routers.auth.user_crud.get_user_by_email", return_value=mock_user):
        response = client.post("/auth/signup", json=payload)
        assert response.status_code == 400
        assert response.json()["detail"] == "Email already registered"

def test_login_success():
    form_data = {"username": "test@test.com", "password": "correct_pass"}
    mock_user = create_mock_user(id="u1", email="test@test.com")
    mock_user.password_hash = "hashed"
    
    with patch("app.routers.auth.user_crud.get_user_by_email", return_value=mock_user):
        with patch("app.routers.auth.auth_service.verify_password", return_value=True):
            with patch("app.routers.auth.auth_service.create_access_token", return_value="token123"):
                response = client.post("/auth/token", data=form_data)
                assert response.status_code == 200
                assert response.json()["access_token"] == "token123"

def test_login_invalid_credentials():
    form_data = {"username": "test@test.com", "password": "wrong_pass"}
    
    # Case 1: User found, pass wrong
    mock_user = create_mock_user(id="u1")
    mock_user.password_hash = "hash"
    
    with patch("app.routers.auth.user_crud.get_user_by_email", return_value=mock_user):
        with patch("app.routers.auth.auth_service.verify_password", return_value=False):
            response = client.post("/auth/token", data=form_data)
            assert response.status_code == 401

    # Case 2: User not found
    with patch("app.routers.auth.user_crud.get_user_by_email", return_value=None):
        response = client.post("/auth/token", data=form_data)
        assert response.status_code == 401

def test_request_otp_success():
    payload = {"email": "test@test.com"}
    mock_user = create_mock_user(id="u1")
    
    with patch("app.routers.auth.user_crud.get_user_by_email", return_value=mock_user):
        with patch("app.routers.auth.auth_crud.create_reset_otp") as mock_create:
            response = client.post("/auth/request-otp", json=payload)
            assert response.status_code == 200
            mock_create.assert_called_once()

def test_verify_otp_success():
    payload = {"email": "test@test.com", "otp": "123456"}
    
    with patch("app.routers.auth.auth_crud.get_valid_otp", return_value=MagicMock()):
        response = client.post("/auth/verify-otp", json=payload)
        assert response.status_code == 200
        assert "verified" in response.json()["message"]

def test_verify_otp_fail():
    payload = {"email": "test@test.com", "otp": "123456"}
    
    with patch("app.routers.auth.auth_crud.get_valid_otp", return_value=None):
        response = client.post("/auth/verify-otp", json=payload)
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid or expired OTP."

def test_reset_password_success():
    payload = {"email": "test@test.com", "otp": "123456", "new_password": "newpass123"}
    mock_otp = MagicMock()
    mock_otp.user = create_mock_user(id="u1")
    
    with patch("app.routers.auth.auth_crud.get_valid_otp", return_value=mock_otp):
        with patch("app.routers.auth.auth_crud.update_user_password") as mock_update:
            with patch("app.routers.auth.auth_crud.delete_otp") as mock_delete:
                response = client.post("/auth/reset-password", json=payload)
                assert response.status_code == 200
                mock_update.assert_called_once()
                mock_delete.assert_called_once()
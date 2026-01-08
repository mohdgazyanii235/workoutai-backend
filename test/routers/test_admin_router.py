import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app
from app import models, schemas
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key, get_current_admin
from app.database import get_db
from datetime import datetime

client = TestClient(app)

# Mock Admin User
mock_admin = models.User(id="admin-id", email="admin@example.com", is_admin=True)
mock_user = models.User(id="user-id", email="user@example.com", is_admin=False)

def override_get_api_key():
    return "valid-api-key"

def override_get_db():
    return MagicMock()

app.dependency_overrides[get_api_key] = override_get_api_key
app.dependency_overrides[get_db] = override_get_db

# --- Tests ---

def test_get_metrics_success():
    app.dependency_overrides[get_current_admin] = lambda: mock_admin
    
    # Mock data: Tuple of (AppMetric, email)
    mock_metric = models.AppMetric(
        id="m1", user_id="u1", last_app_query=datetime.now(), total_api_calls=10
    )
    mock_data = [(mock_metric, "user@test.com")]
    
    with patch("app.routers.admin.admin_crud.get_all_app_metrics", return_value=mock_data):
        response = client.get("/admin/metrics")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_email"] == "user@test.com"
        assert data[0]["metric"]["total_api_calls"] == 10

def test_get_metrics_forbidden():
    # Simulate dependency failure for non-admin
    # In reality, the dependency raises 403, so we verify that behavior if we override with a normal user
    # BUT get_current_admin raises HTTPException itself.
    
    # We must reset the override to use the real function logic or a mock that raises
    def mock_get_current_admin_fail():
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin privileges required")

    app.dependency_overrides[get_current_admin] = mock_get_current_admin_fail
    
    response = client.get("/admin/metrics")
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"

def test_get_total_users_count():
    app.dependency_overrides[get_current_admin] = lambda: mock_admin
    
    with patch("app.routers.admin.user_crud.get_total_user_count", return_value=100):
        response = client.get("/admin/stats/users/count")
        assert response.status_code == 200
        assert response.json() == 100

def test_get_users_list():
    app.dependency_overrides[get_current_admin] = lambda: mock_admin
    mock_users = [
        models.User(id="u1", email="a@a.com"),
        models.User(id="u2", email="b@b.com")
    ]
    
    with patch("app.routers.admin.user_crud.get_all_users_lite", return_value=mock_users):
        response = client.get("/admin/users")
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["email"] == "a@a.com"

def test_send_admin_notification():
    app.dependency_overrides[get_current_admin] = lambda: mock_admin
    payload = {
        "target_user_ids": ["u1", "u2"],
        "title": "Alert",
        "message": "Update"
    }
    
    with patch("app.routers.admin.notification_crud.send_push_notification") as mock_send:
        response = client.post("/admin/notify", json=payload)
        assert response.status_code == 200
        assert "Sent 2 notifications" in response.json()["message"]
        mock_send.assert_called_once_with(["u1", "u2"], "Alert", "Update")
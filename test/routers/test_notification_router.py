import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
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

def test_get_my_notifications():
    mock_notif = models.Notification(
        id="n1", recipient_id="u1", type="TEST", title="T", message="M", is_read=False, created_at=datetime.now(timezone.utc)
    )
    
    with patch("app.routers.notifications.notification_crud.get_notifications", return_value=[mock_notif]):
        response = client.get("/notifications/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "n1"

def test_mark_as_read_success():
    mock_notif = models.Notification(
        id="n1", recipient_id="u1", type="TEST", title="T", message="M", is_read=True, created_at=datetime.now(timezone.utc)
    )
    
    with patch("app.routers.notifications.notification_crud.mark_notification_read", return_value=mock_notif):
        response = client.patch("/notifications/n1/read")
        assert response.status_code == 200
        assert response.json()["is_read"] is True

def test_mark_as_read_not_found():
    with patch("app.routers.notifications.notification_crud.mark_notification_read", return_value=None):
        response = client.patch("/notifications/n1/read")
        assert response.status_code == 404

def test_mark_all_as_read():
    with patch("app.routers.notifications.notification_crud.mark_all_notifications_read"):
        response = client.post("/notifications/mark-all-read")
        assert response.status_code == 200
        assert response.json()["message"] == "All notifications marked as read"
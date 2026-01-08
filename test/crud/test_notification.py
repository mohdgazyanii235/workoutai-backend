import pytest
from unittest.mock import MagicMock, patch
from app import models
from app.crud import notification as crud_notification

@patch("app.crud.notification.send_push_notification")
def test_create_notification_success(mock_send_push, mock_db):
    """Test saving to DB and triggering push."""
    result = crud_notification.create_notification(
        mock_db, 
        recipient_id="r1", 
        type="TEST", 
        title="Hi", 
        message="Msg"
    )
    
    assert isinstance(result, models.Notification)
    assert result.recipient_id == "r1"
    
    # DB Save
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    
    # Push Trigger
    mock_send_push.assert_called_once_with(["r1"], "Hi", "Msg")

@patch("app.crud.notification.requests.post")
def test_send_push_notification_http(mock_post):
    """Test the HTTP request logic for NativeNotify."""
    crud_notification.send_push_notification(["u1"], "Title", "Body")
    
    mock_post.assert_called_once()
    args = mock_post.call_args
    assert args[1]['json']['subIDs'] == ["u1"]
    assert args[1]['json']['title'] == "Title"

def test_mark_notification_read(mock_db):
    """Test marking as read."""
    notif = models.Notification(id="n1", is_read=False)
    mock_db.query.return_value.filter.return_value.first.return_value = notif
    
    result = crud_notification.mark_notification_read(mock_db, "n1", "u1")
    
    assert result.is_read is True
    mock_db.commit.assert_called()

def test_mark_all_read(mock_db):
    """Test bulk update."""
    crud_notification.mark_all_notifications_read(mock_db, "u1")
    
    # Verify update() was called on query
    mock_db.query.return_value.filter.return_value.update.assert_called_with({"is_read": True})
    mock_db.commit.assert_called()
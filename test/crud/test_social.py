import pytest
from unittest.mock import MagicMock, patch
from app import models
from app.crud import social as crud_social

# --- Friendship Status Tests ---

def test_get_friendship_status_none(mock_db):
    """Test that 'none' is returned when no friendship exists in either direction."""
    # Setup: Query returns None (for both checks if needed)
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    status = crud_social.get_friendship_status(mock_db, "user_a", "user_b")
    assert status == "none"

def test_get_friendship_status_pending_sent(mock_db):
    """Test when User A has sent a request to User B."""
    mock_friendship = models.Friendship(requester_id="user_a", addressee_id="user_b", status="pending")
    
    # The first query checks A->B. We make it return the friendship.
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_friendship]
    
    status = crud_social.get_friendship_status(mock_db, "user_a", "user_b")
    assert status == "pending_sent"

def test_get_friendship_status_pending_received(mock_db):
    """Test when User B has sent a request to User A (User A received it)."""
    mock_friendship = models.Friendship(requester_id="user_b", addressee_id="user_a", status="pending")
    
    # First query (A->B) returns None. Second query (B->A) returns friendship.
    mock_db.query.return_value.filter.return_value.first.side_effect = [None, mock_friendship]
    
    status = crud_social.get_friendship_status(mock_db, "user_a", "user_b")
    assert status == "pending_received"

def test_get_friendship_status_accepted(mock_db):
    """Test status is 'accepted' regardless of who sent it."""
    mock_friendship = models.Friendship(requester_id="user_a", addressee_id="user_b", status="accepted")
    mock_db.query.return_value.filter.return_value.first.return_value = mock_friendship
    
    status = crud_social.get_friendship_status(mock_db, "user_a", "user_b")
    assert status == "accepted"

# --- Send Friend Request Tests ---

@patch("app.crud.social.crud_notification")
@patch("app.crud.social.crud_user")
def test_send_friend_request_success(mock_crud_user, mock_crud_notif, mock_db):
    """Test sending a fresh friend request creates DB record and notification."""
    # Setup: No existing friendship
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    # Mock requester user for notification message context
    mock_user = models.User(id="user_a", first_name="Alice")
    mock_crud_user.get_user.return_value = mock_user
    
    # Act
    result = crud_social.send_friend_request(mock_db, "user_a", "user_b")
    
    # Assert
    assert result.requester_id == "user_a"
    assert result.addressee_id == "user_b"
    assert result.status == "pending"
    
    # Verify DB persistence
    mock_db.add.assert_called()
    mock_db.commit.assert_called()
    
    # Verify Notification
    mock_crud_notif.create_notification.assert_called_once()
    call_kwargs = mock_crud_notif.create_notification.call_args.kwargs
    assert call_kwargs['recipient_id'] == "user_b"
    assert call_kwargs['sender_id'] == "user_a"
    assert call_kwargs['type'] == "FRIEND_REQUEST"

def test_send_friend_request_existing(mock_db):
    """Test that if a request already exists, we simply return it without creating a new one."""
    existing = models.Friendship(id="f1", requester_id="user_a", addressee_id="user_b")
    mock_db.query.return_value.filter.return_value.first.return_value = existing
    
    result = crud_social.send_friend_request(mock_db, "user_a", "user_b")
    
    assert result == existing
    mock_db.add.assert_not_called()

# --- Respond to Friend Request Tests ---

@patch("app.crud.social.crud_notification")
@patch("app.crud.social.crud_user")
def test_respond_accept_success(mock_crud_user, mock_crud_notif, mock_db):
    """Test accepting a request updates status and notifies the original sender."""
    # Setup: Pending friendship where current user is the addressee
    friendship = models.Friendship(id="f1", requester_id="user_a", addressee_id="user_b", status="pending")
    mock_db.query.return_value.filter.return_value.first.return_value = friendship
    
    # Mock user for notification
    mock_user = models.User(id="user_b", first_name="Bob")
    mock_crud_user.get_user.return_value = mock_user
    
    # Act
    result = crud_social.respond_to_friend_request(mock_db, "user_b", "f1", "accept")
    
    # Assert
    assert result.status == "accepted"
    mock_db.commit.assert_called()
    
    # Notification sent to requester (Alice)
    mock_crud_notif.create_notification.assert_called_once()
    assert mock_crud_notif.create_notification.call_args.kwargs['recipient_id'] == "user_a" # Alice gets notified
    assert mock_crud_notif.create_notification.call_args.kwargs['type'] == "FRIEND_ACCEPT"

def test_respond_reject_success(mock_db):
    """Test rejecting a request deletes the friendship record."""
    friendship = models.Friendship(id="f1", requester_id="user_a", addressee_id="user_b", status="pending")
    mock_db.query.return_value.filter.return_value.first.return_value = friendship
    
    result = crud_social.respond_to_friend_request(mock_db, "user_b", "f1", "reject")
    
    mock_db.delete.assert_called_with(friendship)
    mock_db.commit.assert_called()

def test_respond_unauthorized(mock_db):
    """Test that a user cannot accept a request meant for someone else."""
    # Friendship is for user_b, but user_c tries to accept
    friendship = models.Friendship(id="f1", requester_id="user_a", addressee_id="user_b", status="pending")
    mock_db.query.return_value.filter.return_value.first.return_value = friendship
    
    result = crud_social.respond_to_friend_request(mock_db, "user_c", "f1", "accept")
    
    assert result is None
    mock_db.commit.assert_not_called()

def test_respond_not_found(mock_db):
    """Test response to non-existent friendship ID."""
    mock_db.query.return_value.filter.return_value.first.return_value = None
    result = crud_social.respond_to_friend_request(mock_db, "u1", "bad_id", "accept")
    assert result is None

# --- Remove Friend Tests ---

def test_remove_friend_success(mock_db):
    """Test removing a friend deletes the record and cascade checks Close Friends."""
    # Setup: Friendship exists
    friendship = models.Friendship(id="f1", status="accepted")
    mock_db.query.return_value.filter.return_value.first.return_value = friendship
    
    # Act
    result = crud_social.remove_friend(mock_db, "u1", "u2")
    
    # Assert
    assert result is True
    mock_db.delete.assert_called_with(friendship)
    # Check that it also attempts to delete CloseFriend links (it calls delete() on a query)
    assert mock_db.query.return_value.filter.return_value.delete.called
    mock_db.commit.assert_called()

def test_remove_friend_not_found(mock_db):
    """Test removing two users who are not friends returns False."""
    mock_db.query.return_value.filter.return_value.first.return_value = None
    result = crud_social.remove_friend(mock_db, "u1", "u2")
    assert result is False

# --- Close Friend Logic ---

def test_toggle_close_friend_add_success(mock_db):
    """Test adding a close friend works if they are already buddies."""
    # Mock get_friendship_status to return 'accepted'
    with patch("app.crud.social.get_friendship_status", return_value="accepted"):
        # Mock check_is_close_friend to False so it adds
        with patch("app.crud.social.check_is_close_friend", return_value=False):
            
            crud_social.toggle_close_friend(mock_db, "u1", "u2", is_close=True)
            
            # Should add a CloseFriend record
            mock_db.add.assert_called()
            args = mock_db.add.call_args[0][0]
            assert isinstance(args, models.CloseFriend)
            assert args.owner_id == "u1"
            assert args.friend_id == "u2"
            mock_db.commit.assert_called()

def test_toggle_close_friend_not_buddies(mock_db):
    """Test validation: cannot add close friend if not accepted friends."""
    with patch("app.crud.social.get_friendship_status", return_value="none"):
        with pytest.raises(ValueError, match="You must be buddies"):
            crud_social.toggle_close_friend(mock_db, "u1", "u2", is_close=True)

def test_toggle_close_friend_remove(mock_db):
    """Test removing a close friend."""
    with patch("app.crud.social.get_friendship_status", return_value="accepted"):
        
        crud_social.toggle_close_friend(mock_db, "u1", "u2", is_close=False)
        
        # Should call delete on the query object
        mock_db.query.return_value.filter.return_value.delete.assert_called()
        mock_db.commit.assert_called()

# --- Interaction Limits (Nudge/Spot) ---

@patch("app.crud.social.crud_notification")
@patch("app.crud.social.crud_user")
def test_perform_social_action_success(mock_crud_user, mock_crud_notif, mock_db):
    """Test successful nudge/spot when limits are not reached."""
    # Setup: Weekly count < 3
    with patch("app.crud.social.get_weekly_interaction_count", return_value=2):
        
        # Mock recent interaction check (daily limit) -> returns None (no spam)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock users for message generation
        mock_sender = models.User(id="s1", first_name="Sender")
        mock_recipient = models.User(id="r1", first_name="Recipient", nudge_count=0)
        mock_crud_user.get_user.side_effect = [mock_recipient, mock_sender]
        
        # Act
        crud_social.perform_social_action(mock_db, "s1", "r1", "nudge")
        
        # Assert
        # Interaction recorded
        mock_db.add.assert_called() 
        # Recipient count incremented
        assert mock_recipient.nudge_count == 1
        # Notification sent
        mock_crud_notif.create_notification.assert_called()
        assert mock_crud_notif.create_notification.call_args.kwargs['type'] == "NUDGE"

def test_perform_social_action_weekly_limit(mock_db):
    """Test error raised when weekly limit (3) is reached."""
    with patch("app.crud.social.get_weekly_interaction_count", return_value=3):
        with pytest.raises(ValueError, match="You have used all your nudges"):
            crud_social.perform_social_action(mock_db, "s1", "r1", "nudge")

def test_perform_social_action_daily_limit(mock_db):
    """Test error raised when spamming (interaction exists within 24h)."""
    with patch("app.crud.social.get_weekly_interaction_count", return_value=1):
        # Simulate an existing interaction found in the last day
        mock_recent = models.UserInteraction(id="prev_interaction")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_recent
        
        with pytest.raises(ValueError, match="You already sent a nudge"):
            crud_social.perform_social_action(mock_db, "s1", "r1", "nudge")
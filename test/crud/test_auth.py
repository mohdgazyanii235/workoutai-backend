import pytest
from unittest.mock import MagicMock, patch
from app import models
from app.crud import auth as crud_auth
from datetime import datetime, timezone, timedelta

def test_create_reset_otp(mock_db):
    """Test it deletes old OTPs and creates a new one."""
    user = models.User(id="u1")
    
    result = crud_auth.create_reset_otp(mock_db, user, "123456")
    
    # Should delete old ones first
    mock_db.query.return_value.filter.return_value.delete.assert_called_once()
    
    # Should add new one
    mock_db.add.assert_called_once()
    assert result.otp_code == "123456"
    assert result.user_id == "u1"

def test_get_valid_otp_success(mock_db):
    """Test retrieving valid OTP."""
    # 1. Mock finding user
    mock_user = models.User(id="u1")
    
    # Mocking the query chain for OTP
    mock_otp = models.PasswordResetOTP(otp_code="123456")
    
    # FIX: Use patch directly, not pytest.mock.patch
    with patch("app.crud.auth.crud_user.get_user_by_email", return_value=mock_user):
        mock_db.query.return_value.filter.return_value.first.return_value = mock_otp
        
        result = crud_auth.get_valid_otp(mock_db, "test@test.com", "123456")
        assert result == mock_otp

def test_get_valid_otp_user_not_found(mock_db):
    """Test fails if user email invalid."""
    # FIX: Use patch directly
    with patch("app.crud.auth.crud_user.get_user_by_email", return_value=None):
        result = crud_auth.get_valid_otp(mock_db, "bad@test.com", "123456")
        assert result is None

def test_update_user_password(mock_db):
    """Test password hash update."""
    user = models.User(id="u1", password_hash="old")
    
    # FIX: Use patch directly
    with patch("app.crud.auth.auth_service.get_password_hash", return_value="new_hashed"):
        
        result = crud_auth.update_user_password(mock_db, user, "new_pass")
        
        assert result.password_hash == "new_hashed"
        mock_db.commit.assert_called_once()
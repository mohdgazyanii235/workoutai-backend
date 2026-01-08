import pytest
from unittest.mock import MagicMock, patch
from app import models, schemas
from app.crud import user as crud_user
from datetime import date

def test_get_user(mock_db):
    mock_user = models.User(id="u1")
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    assert crud_user.get_user(mock_db, "u1") == mock_user

def test_create_user(mock_db):
    user_data = schemas.user.UserCreate(email="test@test.com", password="pw")
    
    # FIX: Use patch directly
    with patch("app.auth.auth_service.get_password_hash", return_value="hashed"):
        result = crud_user.create_user(mock_db, user_data)
        
        assert result.email == "test@test.com"
        assert result.password_hash == "hashed"
        assert result.is_onboarded is False
        mock_db.add.assert_called()

def test_update_user_profile_simple(mock_db):
    """Test simple field update."""
    mock_user = models.User(id="u1", city="Old City")
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    
    update = schemas.user.UserUpdate(city="New City")
    
    result = crud_user.update_user_profile(mock_db, "u1", update)
    
    assert result.city == "New City"
    assert result.is_onboarded is True # Side effect of update
    mock_db.commit.assert_called()

def test_update_user_profile_history_field(mock_db):
    """Test appending to a history list (e.g. weight)."""
    # Setup user with empty weight history
    mock_user = models.User(id="u1", weight=[])
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    
    # Update with new weight entry
    entry = schemas.user.HistoryEntry(date=date(2023, 1, 1), value=80.5)
    update = schemas.user.UserUpdate(weight=[entry])
    
    result = crud_user.update_user_profile(mock_db, "u1", update)
    
    # Assert
    assert len(result.weight) == 1
    # Check conversion to dict/isoformat happened
    assert result.weight[0]['value'] == 80.5
    assert result.weight[0]['date'] == "2023-01-01"

def test_update_history_tracked_field_function(mock_db):
    """Test the standalone helper for updating tracked fields."""
    mock_user = models.User(id="u1", bench_1rm=[])
    
    crud_user.update_history_tracked_field(mock_db, mock_user, 100.0, "2023-01-01", "bench_1rm")
    
    assert len(mock_user.bench_1rm) == 1
    assert mock_user.bench_1rm[0]['value'] == 100.0
    mock_db.commit.assert_called()
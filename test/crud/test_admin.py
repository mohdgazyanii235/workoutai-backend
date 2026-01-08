import pytest
from unittest.mock import MagicMock
from app import models
from app.crud import admin as crud_admin

# --- log_app_metric ---

def test_log_app_metric_new_user(mock_db):
    """Test creating a new metric record for a user who doesn't have one."""
    user_id = "user-1"
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    result = crud_admin.log_app_metric(mock_db, user_id)
    
    assert isinstance(result, models.AppMetric)
    assert result.user_id == user_id
    assert result.total_api_calls == 1
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()

def test_log_app_metric_existing_user(mock_db):
    """Test incrementing the counter for an existing metric record."""
    user_id = "user-1"
    existing_metric = models.AppMetric(user_id=user_id, total_api_calls=5)
    mock_db.query.return_value.filter.return_value.first.return_value = existing_metric
    
    result = crud_admin.log_app_metric(mock_db, user_id)
    
    assert result.total_api_calls == 6
    mock_db.add.assert_not_called() # Should update in place
    mock_db.commit.assert_called_once()

def test_log_app_metric_error(mock_db):
    """Test error handling during logging."""
    mock_db.query.side_effect = Exception("DB Error")
    
    result = crud_admin.log_app_metric(mock_db, "u1")
    
    assert result is None
    mock_db.rollback.assert_called_once()

# --- log_rubbish_voice_log ---

def test_log_rubbish_voice_log_increment(mock_db):
    """Test incrementing rubbish voice logs."""
    user_id = "u1"
    metric = models.AppMetric(user_id=user_id, rubbish_voice_logs=2)
    mock_db.query.return_value.filter.return_value.first.return_value = metric
    
    result = crud_admin.log_rubbish_voice_log(mock_db, user_id)
    
    assert result.rubbish_voice_logs == 3
    mock_db.commit.assert_called()

def test_log_rubbish_voice_log_init(mock_db):
    """Test initializing count if None."""
    metric = models.AppMetric(user_id="u1", rubbish_voice_logs=None)
    mock_db.query.return_value.filter.return_value.first.return_value = metric
    
    result = crud_admin.log_rubbish_voice_log(mock_db, "u1")
    assert result.rubbish_voice_logs == 1

# --- log_open_ai_query ---

def test_log_open_ai_query_increment(mock_db):
    """Test incrementing open ai call count."""
    metric = models.AppMetric(user_id="u1", open_ai_calls=10)
    mock_db.query.return_value.filter.return_value.first.return_value = metric
    
    result = crud_admin.log_open_ai_query(mock_db, "u1")
    assert result.open_ai_calls == 11

# --- get_all_app_metrics ---

def test_get_all_app_metrics(mock_db):
    """Test joining metrics with user emails."""
    mock_data = [(models.AppMetric(user_id="u1"), "test@test.com")]
    mock_db.query.return_value.join.return_value.all.return_value = mock_data
    
    result = crud_admin.get_all_app_metrics(mock_db)
    
    assert len(result) == 1
    assert result[0][1] == "test@test.com"
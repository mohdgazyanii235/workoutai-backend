import pytest
from unittest.mock import MagicMock
from datetime import date, timedelta, datetime, timezone
from app import models, schemas
from app.crud import analytics as crud_analytics

# --- upsert_health_daily ---

def test_upsert_health_daily_create(mock_db):
    """Test creating a new health record for a date."""
    user_id = "u1"
    data = schemas.analytics.HealthDailyCreate(date=date(2023, 1, 1), steps=5000)
    
    # Mock existing query returns None
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    result = crud_analytics.upsert_health_daily(mock_db, user_id, data)
    
    assert result is True
    mock_db.add.assert_called_once()
    args = mock_db.add.call_args[0][0]
    assert args.steps == 5000
    assert args.date == date(2023, 1, 1)

def test_upsert_health_daily_update(mock_db):
    """Test updating existing fields only if provided."""
    user_id = "u1"
    # Existing record has 2000 steps, None calories
    existing = models.HealthDaily(steps=2000, active_calories=None)
    mock_db.query.return_value.filter.return_value.first.return_value = existing
    
    # Update Payload: steps=None (don't change), active_calories=500 (update)
    data = schemas.analytics.HealthDailyCreate(date=date(2023, 1, 1), steps=None, active_calories=500.0)
    
    crud_analytics.upsert_health_daily(mock_db, user_id, data)
    
    assert existing.steps == 2000 # Unchanged
    assert existing.active_calories == 500.0 # Updated
    mock_db.add.assert_not_called()

# --- calculate_momentum_streak ---

def test_calculate_momentum_streak_zero(mock_db):
    """Test streak is 0 if no recent activity."""
    # Setup queries to return empty lists
    mock_db.query.return_value.filter.return_value.all.return_value = []
    
    streak = crud_analytics.calculate_momentum_streak(mock_db, "u1")
    assert streak == 0

def test_calculate_momentum_streak_active_today(mock_db):
    """Test streak counts today if active."""
    today = date.today()
    # Mock health record active today
    active_health = models.HealthDaily(date=today, steps=6000) # > 5000 threshold
    
    mock_db.query.return_value.filter.return_value.all.side_effect = [
        [active_health], # health query
        [] # workout query
    ]
    
    streak = crud_analytics.calculate_momentum_streak(mock_db, "u1")
    assert streak == 1

def test_calculate_momentum_streak_yesterday(mock_db):
    """Test streak counts from yesterday if today is inactive."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    # Active yesterday via Workout
    mock_workout = models.Workout(created_at=datetime.combine(yesterday, datetime.min.time()))
    
    mock_db.query.return_value.filter.return_value.all.side_effect = [
        [], # health query (empty)
        [mock_workout] # workout query
    ]
    
    streak = crud_analytics.calculate_momentum_streak(mock_db, "u1")
    assert streak == 1

def test_calculate_momentum_streak_broken(mock_db):
    """Test streak stops at a gap."""
    today = date.today()
    # Active 2 days ago, but gap yesterday
    two_days_ago = today - timedelta(days=2)
    
    mock_health = models.HealthDaily(date=two_days_ago, steps=10000)
    
    mock_db.query.return_value.filter.return_value.all.side_effect = [[mock_health], []]
    
    streak = crud_analytics.calculate_momentum_streak(mock_db, "u1")
    assert streak == 0 # Gap yesterday breaks it

# --- get_day_view_metrics ---

def test_get_day_view_metrics(mock_db):
    """Test fetching aggregated day metrics."""
    target_date = date(2023, 1, 1)
    
    # Mock Health
    mock_health = models.HealthDaily(date=target_date, steps=5000, active_calories=400)
    
    # Mock Workouts (separate query)
    # FIX: Populate required fields for Pydantic validation (created_at, user_id, visibility)
    mock_workout = models.Workout(
        id="w1", 
        created_at=datetime.now(timezone.utc), 
        user_id="u1", 
        visibility="private",
        notes="Test workout"
    )
    mock_workouts = [mock_workout]
    
    def query_side_effect(model):
        m = MagicMock()
        if model == models.HealthDaily:
            m.filter.return_value.first.return_value = mock_health
        elif model == models.Workout:
            m.filter.return_value.order_by.return_value.all.return_value = mock_workouts
        return m
        
    mock_db.query.side_effect = query_side_effect

    result = crud_analytics.get_day_view_metrics(mock_db, "u1", target_date)
    
    assert result.health_metrics.steps == 5000
    assert len(result.workouts) == 1
    assert result.strain == 1.0 # 400 / 400 = 1.0

# --- get_exercise_progress ---

def test_get_exercise_progress(mock_db):
    """Test 1RM calculation over time."""
    # Set 1: 100kg x 1 rep (1RM ~ 103)
    # Set 2: 100kg x 5 reps (1RM ~ 116) - same day
    
    today = date.today()
    workout = models.Workout(created_at=datetime.combine(today, datetime.min.time()))
    
    s1 = models.ExerciseSet(weight=100, reps=1, workout=workout)
    s2 = models.ExerciseSet(weight=100, reps=5, workout=workout)
    
    mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = [s1, s2]
    
    result = crud_analytics.get_exercise_progress(mock_db, "u1", "Bench")
    
    assert len(result.history) == 1 # Groups by day
    # Should take the max of the day (s2)
    # 1RM formula in code: weight * (1 + reps/30) -> 100 * (1 + 5/30) = 116.66
    assert result.history[0].one_rep_max == 116.7
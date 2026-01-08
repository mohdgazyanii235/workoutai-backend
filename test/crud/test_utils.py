import pytest
from app.crud import utils as crud_utils
from app import models
from datetime import datetime, timedelta, timezone

def test_consistency_score_empty():
    assert crud_utils.calculate_consistency_score([]) == 0.0

def test_consistency_score_single():
    w = models.Workout(created_at=datetime.now(timezone.utc))
    assert crud_utils.calculate_consistency_score([w]) == 100.0

def test_consistency_score_perfect():
    """Test ~12 workouts in last 30 days gives 100%."""
    now = datetime.now(timezone.utc)
    workouts = []
    # Create 15 workouts, one every day for last 15 days
    for i in range(15):
        w = models.Workout(created_at=now - timedelta(days=i))
        workouts.append(w)
        
    score = crud_utils.calculate_consistency_score(workouts)
    assert score == 100.0

def test_consistency_score_low():
    """Test 1 workout in last 30 days gives low score."""
    now = datetime.now(timezone.utc)
    
    # 1 recent, 1 very old
    w1 = models.Workout(created_at=now)
    w2 = models.Workout(created_at=now - timedelta(days=100))
    
    score = crud_utils.calculate_consistency_score([w1, w2])
    
    # Calculation: len(recent) * 8 -> 1 * 8 = 8.0
    assert score == 8.0

def test_consistency_score_gaps():
    """Test calculation if workouts are spread out but few."""
    now = datetime.now(timezone.utc)
    w1 = models.Workout(created_at=now)
    w2 = models.Workout(created_at=now - timedelta(days=5))
    w3 = models.Workout(created_at=now - timedelta(days=10))
    
    score = crud_utils.calculate_consistency_score([w1, w2, w3])
    # 3 * 8 = 24
    assert score == 24.0
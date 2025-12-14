import datetime

def calculate_consistency_score(workouts: list) -> float:
    # Simplified version of what you had in frontend
    if not workouts:
        return 0.0
    
    if len(workouts) == 1:
        return 100.0
        
    # Ensure we are working with valid dates
    valid_workouts = [w for w in workouts if w.created_at]
    if not valid_workouts:
        return 0.0

    sorted_dates = sorted([w.created_at for w in valid_workouts])
    
    # Get unique workout days
    unique_days = set(d.date() for d in sorted_dates)
    if len(unique_days) < 2:
        return 100.0
        
    # Calculate gaps
    total_days = (sorted_dates[-1] - sorted_dates[0]).days
    if total_days == 0: return 100.0
    
    # FIX: Use offset-aware UTC time for comparison
    thirty_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    
    recent_workouts = [w for w in valid_workouts if w.created_at >= thirty_days_ago]
    score = min(len(recent_workouts) * 8, 100) # 12 workouts a month = ~100%
    return float(score)
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, extract, or_, and_
from app import models, schemas
from app.schemas import analytics as analytics_schemas
from app.schemas import workout as workout_schemas
import uuid
from datetime import date, timedelta
import datetime

def upsert_health_daily(db: Session, user_id: str, data: analytics_schemas.HealthDailyCreate):
    # Check if record exists for this day
    existing = db.query(models.HealthDaily).filter(
        models.HealthDaily.user_id == user_id,
        models.HealthDaily.date == data.date
    ).first()

    if existing:
        # Update existing fields if they are provided in the payload (non-null)
        if data.steps is not None: existing.steps = data.steps
        if data.active_calories is not None: existing.active_calories = data.active_calories
        if data.exercise_minutes is not None: existing.exercise_minutes = data.exercise_minutes
        if data.resting_hr is not None: existing.resting_hr = data.resting_hr
        if data.avg_heart_rate is not None: existing.avg_heart_rate = data.avg_heart_rate
        if data.hrv is not None: existing.hrv = data.hrv
        if data.vo2_max is not None: existing.vo2_max = data.vo2_max
        if data.walking_hr_avg is not None: existing.walking_hr_avg = data.walking_hr_avg
        existing.updated_at = datetime.datetime.utcnow()
    else:
        # Create new
        new_record = models.HealthDaily(
            id=str(uuid.uuid4()),
            user_id=user_id,
            date=data.date,
            steps=data.steps,
            active_calories=data.active_calories,
            exercise_minutes=data.exercise_minutes,
            resting_hr=data.resting_hr,
            avg_heart_rate=data.avg_heart_rate,
            hrv=data.hrv,
            vo2_max=data.vo2_max,
            walking_hr_avg=data.walking_hr_avg
        )
        db.add(new_record)
    
    db.commit()
    return True

def get_day_view_metrics(db: Session, user_id: str, target_date: date) -> analytics_schemas.DayViewMetrics:
    # 1. Fetch Health Metrics
    daily_health = db.query(models.HealthDaily).filter(
        models.HealthDaily.user_id == user_id,
        models.HealthDaily.date == target_date
    ).first()

    health_schema = None
    strain = 0.0
    
    if daily_health:
        health_schema = analytics_schemas.HealthDailyCreate(
            date=daily_health.date,
            steps=daily_health.steps,
            active_calories=daily_health.active_calories,
            exercise_minutes=daily_health.exercise_minutes,
            resting_hr=daily_health.resting_hr,
            avg_heart_rate=daily_health.avg_heart_rate,
            hrv=daily_health.hrv,
            vo2_max=daily_health.vo2_max,
            walking_hr_avg=daily_health.walking_hr_avg
        )
        # Simple Strain Calc: (active cals / 2000) * 10, capped at 10. Placeholder.
        # If we have proprietary score, use it.
        if daily_health.physical_effort_score:
            strain = daily_health.physical_effort_score
        else:
            strain = min((daily_health.active_calories or 0) / 400, 10.0)

    # 2. Fetch Workouts for that specific day (Owned + Joined)
    # We need to filter based on the date part of created_at
    # SQLAlchemy casting to date works for PostgreSQL
    
    # Updated to fetch joined workouts as well
    workouts = db.query(models.Workout).outerjoin(
        models.WorkoutMember,
        and_(
            models.WorkoutMember.workout_id == models.Workout.id,
            models.WorkoutMember.user_id == user_id
        )
    ).filter(
        func.date(models.Workout.created_at) == target_date,
        or_(
            models.Workout.user_id == user_id,
            models.WorkoutMember.status == 'accepted'
        )
    ).order_by(models.Workout.created_at.desc()).all()

    return analytics_schemas.DayViewMetrics(
        date=target_date,
        health_metrics=health_schema,
        workouts=workouts,
        strain=round(strain, 1)
    )

def calculate_momentum_streak(db: Session, user_id: str) -> int:
    """
    Counts consecutive days backwards from yesterday/today where the user was 'active'.
    Active = logged a workout OR > 300 active calories OR > 5000 steps.
    """
    # Fetch last 30 days of health data + workouts
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    
    health_records = db.query(models.HealthDaily).filter(
        models.HealthDaily.user_id == user_id,
        models.HealthDaily.date >= thirty_days_ago
    ).all()
    
    workouts = db.query(models.Workout).outerjoin(
        models.WorkoutMember,
        and_(
            models.WorkoutMember.workout_id == models.Workout.id,
            models.WorkoutMember.user_id == user_id
        )
    ).filter(
        models.Workout.created_at >= thirty_days_ago,
        or_(
            models.Workout.user_id == user_id,
            models.WorkoutMember.status == 'accepted'
        )
    ).all()
    
    # Map activity by date
    activity_map = {} # date -> bool
    
    for rec in health_records:
        is_active = (rec.steps and rec.steps > 5000) or (rec.active_calories and rec.active_calories > 300)
        if is_active:
            activity_map[rec.date] = True
            
    for w in workouts:
        w_date = w.created_at.date()
        activity_map[w_date] = True
        
    # Calculate streak
    streak = 0
    
    check_date = today
    if activity_map.get(check_date):
        streak += 1
        check_date -= timedelta(days=1)
    else:
        # If today isn't active yet, start checking from yesterday
        check_date -= timedelta(days=1)
        
    while True:
        if activity_map.get(check_date):
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
            
    return streak

def get_dashboard_metrics(db: Session, user_id: str) -> analytics_schemas.DashboardMetrics:
    today = date.today()
    
    # 1. Get today's health record
    daily = db.query(models.HealthDaily).filter(
        models.HealthDaily.user_id == user_id,
        models.HealthDaily.date == today
    ).first()
    
    load_val = 0
    hrv_val = None
    rhr_val = None
    vo2_val = None
    
    if daily:
        cal_score = min((daily.active_calories or 0) / 10, 60) 
        step_score = min((daily.steps or 0) / 200, 40) 
        load_val = int(cal_score + step_score)
        hrv_val = daily.hrv
        rhr_val = daily.resting_hr
        vo2_val = daily.vo2_max

    # 2. Recovery Score
    recovery_score = 0
    if hrv_val:
        avg_hrv = db.query(func.avg(models.HealthDaily.hrv)).filter(
            models.HealthDaily.user_id == user_id,
            models.HealthDaily.hrv.isnot(None)
        ).scalar() or hrv_val
        ratio = hrv_val / avg_hrv
        if ratio >= 1.2: recovery_score = 95
        elif ratio >= 1.0: recovery_score = 75
        elif ratio >= 0.8: recovery_score = 50
        else: recovery_score = 25

    # 3. Momentum Streak
    streak = calculate_momentum_streak(db, user_id)
    
    # 4. NEW: Activity History (Last 21 Days for Pagination)
    # We want to provide 3 pages of 7 dots
    lookback_days = 21
    start_date = today - timedelta(days=lookback_days - 1)
    
    # Fetch all activity in one go
    health_history = db.query(models.HealthDaily.date, models.HealthDaily.steps, models.HealthDaily.active_calories).filter(
        models.HealthDaily.user_id == user_id,
        models.HealthDaily.date >= start_date
    ).all()
    
    workout_history = db.query(func.date(models.Workout.created_at)).outerjoin(
        models.WorkoutMember,
        and_(
            models.WorkoutMember.workout_id == models.Workout.id,
            models.WorkoutMember.user_id == user_id
        )
    ).filter(
        models.Workout.created_at >= start_date,
        or_(
            models.Workout.user_id == user_id,
            models.WorkoutMember.status == 'accepted'
        )
    ).all()
    
    # Map for easy O(1) lookup
    activity_map = {}
    for d, s, c in health_history:
        if (s and s > 5000) or (c and c > 300):
            activity_map[d] = True
    for (w_date,) in workout_history:
        activity_map[w_date] = True

    history_list = []
    for i in range(lookback_days):
        current_date = start_date + timedelta(days=i)
        history_list.append({
            "date": current_date,
            "active": activity_map.get(current_date, False)
        })

    # 5. Dynamic Message
    msg = "Let's get moving!"
    if recovery_score > 70: msg = "Your body is primed. Go for a PR!"
    elif recovery_score < 40 and recovery_score > 0: msg = "Focus on rest or light cardio today."
    elif streak > 3: msg = f"{streak} day streak! Keep it up!"

    # print("\n\n\n PRINTING HISTORY\n\n\n" + history_list)

    return analytics_schemas.DashboardMetrics(
        load_score=min(load_val, 100),
        recovery_score=recovery_score,
        momentum_streak=streak,
        activity_history=history_list,
        resting_hr=rhr_val,
        hrv=hrv_val,
        vo2_max=vo2_val,
        message=msg
    )


def get_exercise_progress(db: Session, user_id: str, exercise_name: str) -> analytics_schemas.ExerciseProgressResponse:
    # Fetch all sets for this exercise, ordered by date
    sets = db.query(models.ExerciseSet).join(models.Workout).filter(
        models.Workout.user_id == user_id,
        models.ExerciseSet.exercise_name.ilike(exercise_name)
    ).order_by(models.Workout.created_at.asc()).all()
    
    history = []
    
    workout_map = {} # date -> max_1rm
    
    for s in sets:
        w_date = s.workout.created_at.date()
        est_1rm = s.weight * (1 + s.reps / 30)
        
        if w_date not in workout_map:
            workout_map[w_date] = 0
        
        if est_1rm > workout_map[w_date]:
            workout_map[w_date] = est_1rm
            
    for d, val in workout_map.items():
        history.append(analytics_schemas.ExerciseHistoryPoint(date=d, one_rep_max=round(val, 1), volume=0)) 
        
    return analytics_schemas.ExerciseProgressResponse(
        exercise_name=exercise_name,
        history=history
    )

def get_all_workout_dates(db: Session, user_id: str) -> list[date]:
    """
    Fetches every unique date a user has performed OR joined a workout for the calendar view.
    """
    # Use func.date to truncate the timestamp to a date object at the DB level
    results = db.query(func.date(models.Workout.created_at)).outerjoin(
        models.WorkoutMember,
        and_(
            models.WorkoutMember.workout_id == models.Workout.id,
            models.WorkoutMember.user_id == user_id
        )
    ).filter(
        or_(
            models.Workout.user_id == user_id,
            models.WorkoutMember.status == 'accepted'
        )
    ).distinct().all()
    
    # Flatten the list of tuples [(date,), (date,)] -> [date, date]
    return [r[0] for r in results]
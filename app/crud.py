from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import uuid
from . import models, schemas
from .services.ai_service import VoiceLog
from app.auth import auth_service
from datetime import timezone, timedelta
import datetime
from typing import Optional, List

def get_user(db: Session, id: str):
    return db.query(models.User).filter(models.User.id == id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    """Create minimal user at signup; onboarding fills the rest later."""
    hashed_password = None
    if user.password:
        hashed_password = auth_service.get_password_hash(user.password)

    db_user = models.User(
        id=str(uuid.uuid4()),
        email=user.email,
        password_hash=hashed_password,
        # all profile fields start as NULL
        is_onboarded=False,  # critical: onboarding not completed yet
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_profile(db: Session, user_id: str, update: schemas.UserUpdate):
    db_user = get_user(db, id=user_id)
    if not db_user:
        return None

    update_data = update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field in ["weight", "fat_percentage", "deadlift_1rm", "squat_1rm", "bench_1rm"] and value:
            current = getattr(db_user, field) or []
            normalized = []
            for entry in value:
                if hasattr(entry, "model_dump"):  # Pydantic model
                    data = entry.model_dump()
                else:  # dict
                    data = dict(entry)

                # 🔹 Convert date objects to strings
                if isinstance(data.get("date"), (datetime.date, datetime.datetime)):
                    data["date"] = data["date"].isoformat()

                normalized.append(data)

            current.extend(normalized)
            setattr(db_user, field, current)
        else:
            # Convert date_of_birth too, since it is a Date column (but DB can handle this type)
            setattr(db_user, field, value)

    db_user.is_onboarded = True
    db.commit()
    db.refresh(db_user)
    return db_user


# --- THIS FUNCTION WAS MISSING FROM YOUR LAST FILE ---
def update_workout(
    db: Session,
    workout_id: str,
    workout_update: schemas.WorkoutUpdate,
    user_id: str # Ensure only the owner can update
) -> Optional[models.Workout]:

    # Fetch the existing workout, ensuring it belongs to the current user
    db_workout = db.query(models.Workout).filter(
        models.Workout.id == workout_id,
        models.Workout.user_id == user_id
    ).first()

    if not db_workout:
        return None # Workout not found or doesn't belong to the user

    # 1. Update Workout fields (notes, workout_type) if provided
    update_data = workout_update.model_dump(exclude_unset=True) # Get only fields present in the request
    if "notes" in update_data:
        db_workout.notes = update_data["notes"] # Handles null correctly
    if "workout_type" in update_data:
        db_workout.workout_type = update_data["workout_type"]

    if "visibility" in update_data:
        db_workout.visibility = update_data["visibility"]

    db.add(db_workout)

    # 2. Handle Exercise Sets update if 'sets' field is present in the request
    if workout_update.sets is not None:
        # Get dictionary of current sets from DB, keyed by their ID
        current_sets_db = {s.id: s for s in db_workout.sets}
        # Keep track of set IDs present in the incoming update payload
        incoming_set_ids = set()

        for set_data in workout_update.sets:
            if set_data.id and set_data.id in current_sets_db:
                # --- UPDATE existing set ---
                db_set = current_sets_db[set_data.id]
                db_set.exercise_name = set_data.exercise_name
                db_set.set_number = set_data.set_number # Update set number
                db_set.reps = set_data.reps
                db_set.weight = set_data.weight
                db_set.weight_unit = set_data.weight_unit
                db.add(db_set) # Mark existing set as modified
                incoming_set_ids.add(set_data.id) # Mark this ID as processed
            elif not set_data.id:
                # --- CREATE new set --- (ID is None or missing)
                db_new_set = models.ExerciseSet(
                    id=str(uuid.uuid4()), # Generate new ID
                    exercise_name=set_data.exercise_name,
                    set_number=set_data.set_number, # Use number from payload
                    reps=set_data.reps,
                    weight=set_data.weight,
                    weight_unit=set_data.weight_unit,
                    workout_id=db_workout.id # Link to the parent workout
                )
                db.add(db_new_set)

        # --- DELETE sets that are in the DB but were NOT in the incoming payload ---
        set_ids_to_delete = current_sets_db.keys() - incoming_set_ids
        for set_id in set_ids_to_delete:
            db.delete(current_sets_db[set_id])

    # --- NEW: Handle Cardio Sessions update ---
    if workout_update.cardio_sessions is not None:
        current_cardio_db = {c.id: c for c in db_workout.cardio_sessions}
        incoming_cardio_ids = set()

        for cardio_data in workout_update.cardio_sessions:
            if cardio_data.id and cardio_data.id in current_cardio_db:
                # --- UPDATE existing cardio session ---
                db_cardio = current_cardio_db[cardio_data.id]
                db_cardio.name = cardio_data.name
                db_cardio.duration_minutes = cardio_data.duration_minutes
                db_cardio.distance = cardio_data.distance
                db_cardio.distance_unit = cardio_data.distance_unit
                db_cardio.speed = cardio_data.speed
                db_cardio.pace = cardio_data.pace
                db_cardio.laps = cardio_data.laps
                db.add(db_cardio)
                incoming_cardio_ids.add(cardio_data.id)
            elif not cardio_data.id:
                # --- CREATE new cardio session ---
                db_new_cardio = models.CardioSession(
                    id=str(uuid.uuid4()),
                    name=cardio_data.name,
                    duration_minutes=cardio_data.duration_minutes,
                    distance=cardio_data.distance,
                    distance_unit=cardio_data.distance_unit,
                    speed=cardio_data.speed,
                    pace=cardio_data.pace,
                    laps=cardio_data.laps,
                    workout_id=db_workout.id
                )
                db.add(db_new_cardio)

        # --- DELETE cardio sessions not in the payload ---
        cardio_ids_to_delete = current_cardio_db.keys() - incoming_cardio_ids
        for cardio_id in cardio_ids_to_delete:
            db.delete(current_cardio_db[cardio_id])


    try:
        db.commit()
        db.refresh(db_workout) # Refresh to load relationships correctly
        return db_workout
    except Exception as e:
        db.rollback() # Rollback in case of error during commit
        print(f"Error updating workout: {e}") # Or use logger
        raise e # Re-raise the exception to be handled by the endpoint


def get_public_workouts_for_user(db: Session, user_id: str, limit: int = 10):
    return db.query(models.Workout).filter(
        models.Workout.user_id == user_id,
        models.Workout.visibility == "public"
    ).order_by(models.Workout.created_at.desc()).limit(limit).all()


# --- THIS FUNCTION WAS MISSING ---
def create_workout_from_log(db: Session, log: VoiceLog, user_id: str, created_at: Optional[datetime.datetime] = None) -> models.Workout:
    db_workout = models.Workout(
        id=str(uuid.uuid4()),
        user_id=user_id,
        notes=log.note,
        workout_type=log.workout_type,
        created_at=created_at
    )
    db.add(db_workout)
    
    # Commit workout first to get its ID
    try:
        db.commit()
        db.refresh(db_workout)
    except Exception as e:
        db.rollback()
        print(f"Error creating parent workout from log: {e}")
        raise e

    if log.sets:
        for i, ai_set in enumerate(log.sets):
            db_exercise_set = models.ExerciseSet(
                id=str(uuid.uuid4()),
                exercise_name=ai_set.exercise_name,
                set_number=ai_set.sets,
                reps=ai_set.reps,
                weight=ai_set.weight,
                weight_unit=ai_set.weight_unit,
                workout_id=db_workout.id
            )
            db.add(db_exercise_set)

    if log.cardio:
        for ai_cardio in log.cardio:
            db_cardio_session = models.CardioSession(
                id=str(uuid.uuid4()),
                name=ai_cardio.exercise_name,
                duration_minutes=ai_cardio.duration_minutes,
                speed=ai_cardio.speed,
                pace=ai_cardio.pace,
                distance=ai_cardio.distance,
                distance_unit=ai_cardio.distance_unit,
                laps=ai_cardio.laps,
                workout_id=db_workout.id
            )
            db.add(db_cardio_session)

    try:
        db.commit()
        db.refresh(db_workout)
    except Exception as e:
        db.rollback()
        print(f"Error creating workout children from log: {e}")
        raise e
        
    return db_workout


def manage_voice_log(db: Session, voice_log: VoiceLog, user_id: str, created_at: Optional[datetime.datetime] = None):
    logging_timestamp = created_at if created_at else datetime.datetime.now(datetime.timezone.utc)
    db_user = get_user(db, id=user_id)
    entry_date = logging_timestamp.date() if logging_timestamp.date() else datetime.date.today()
    date_str = entry_date.isoformat()
    if not db_user:
        print(f"User not found with ID: {user_id}")
        return None

    if voice_log.updated_weight:
        print("User wants to update their weight")
        update_history_tracked_field(db, db_user, voice_log.updated_weight, date_str, "weight")
    
    if voice_log.updated_bench_1rm:
        print("User wants to update their bench 1rm")
        update_history_tracked_field(db, db_user, voice_log.updated_bench_1rm, date_str, "bench_1rm")

    if voice_log.updated_squat_1rm:
        print("User wants to update their squat 1rm")
        update_history_tracked_field(db, db_user, voice_log.updated_squat_1rm, date_str, "squat_1rm")

    if voice_log.updated_deadlift_1rm:
        print("User wants to update their deadlift 1rm")
        update_history_tracked_field(db, db_user, voice_log.updated_deadlift_1rm, date_str, "deadlift_1rm")

    if voice_log.updated_fat_percentage:
        print("User wants to update their fat %")
        update_history_tracked_field(db, db_user, voice_log.updated_fat_percentage, date_str, "fat_percentage")

    # MODIFIED: Check for sets OR cardio
    if (voice_log.sets and len(voice_log.sets) > 0) or (voice_log.cardio and len(voice_log.cardio) > 0):
        print("user wants to log a workout or cardio")
        create_workout_from_log(db, voice_log, user_id, logging_timestamp)

    if not voice_log.updated_weight and not voice_log.updated_bench_1rm and not voice_log.updated_squat_1rm and not voice_log.updated_deadlift_1rm and not voice_log.updated_fat_percentage and not ((voice_log.sets and len(voice_log.sets) > 0) or (voice_log.cardio and len(voice_log.cardio) > 0)):
        log_rubbish_voice_log(db, user_id=user_id)
    

    return voice_log.comment

def update_history_tracked_field(db, db_user, updated_value: float, date_str: str, field_type: str):
    new_entry = {"date": date_str, "value": updated_value}
    current_history: List[dict] = getattr(db_user, field_type) or []
    updated_history = current_history + [new_entry]
    setattr(db_user, field_type, updated_history)
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        db.rollback()
        print(f"Error committing update for user {db_user.id}: {e}")
        raise e



def get_pending_requests(db: Session, user_id: str):
    return db.query(models.Friendship).filter(
        models.Friendship.addressee_id == user_id,
        models.Friendship.status == "pending"
    )


def get_public_user(db: Session, user_id: str):
    return db.query(models.User).filter(models.User.id == user_id).first()

def delete_workout(db: Session, workout_id: str, user_id: str) -> models.Workout | None:
    # First, find the workout to ensure it exists and belongs to the user
    db_workout = (
        db.query(models.Workout)
        .filter(
            models.Workout.id == workout_id,
            models.Workout.user_id == user_id
        )
        .first()
    )
    
    if not db_workout:
        return None  # Workout not found or doesn't belong to user

    # 1. Delete the workout itself.
    # SQLAlchemy will handle deleting child ExerciseSets and CardioSessions
    # because we added `cascade="all, delete-orphan"` to the relationships.
    db.delete(db_workout)
    
    # 2. Commit the transaction
    db.commit()
    
    return db_workout


def create_manual_workout(db: Session, workout_data: schemas.WorkoutUpdate, user_id: str) -> models.Workout:
    # 1. Create the parent Workout
    db_workout = models.Workout(
        id=str(uuid.uuid4()),
        user_id=user_id,
        notes=workout_data.notes,
        workout_type=workout_data.workout_type,
        created_at=datetime.datetime.now(datetime.timezone.utc) # Use current time
    )
    db.add(db_workout)
    
    # --- MODIFICATION: Commit the parent workout FIRST to get its ID ---
    try:
        db.commit()
        db.refresh(db_workout)
    except Exception as e:
        db.rollback()
        print(f"Error creating parent workout: {e}")
        raise e
    # -----------------------------------------------------------------

    # 2. Create the child ExerciseSets
    if workout_data.sets:
        for set_data in workout_data.sets:
            db_exercise_set = models.ExerciseSet(
                id=str(uuid.uuid4()),
                exercise_name=set_data.exercise_name,
                set_number=set_data.set_number,
                reps=set_data.reps,
                weight=set_data.weight,
                weight_unit=set_data.weight_unit,
                workout_id=db_workout.id # Link to the parent workout
            )
            db.add(db_exercise_set)

    # --- NEW: Create the child CardioSessions ---
    if workout_data.cardio_sessions:
        for cardio_data in workout_data.cardio_sessions:
            db_cardio_session = models.CardioSession(
                id=str(uuid.uuid4()),
                name=cardio_data.name,
                duration_minutes=cardio_data.duration_minutes,
                distance=cardio_data.distance,
                distance_unit=cardio_data.distance_unit,
                speed=cardio_data.speed,
                pace=cardio_data.pace,
                laps=cardio_data.laps,
                workout_id=db_workout.id
            )
            db.add(db_cardio_session)

    # 3. Commit the transaction (for children)
    try:
        db.commit()
        db.refresh(db_workout) # Refresh to get all data
        return db_workout
    except Exception as e:
        db.rollback()
        print(f"Error creating manual workout children: {e}") # Modified log
        raise e



def create_reset_otp(db: Session, user: models.User, otp_code: str) -> models.PasswordResetOTP:
    # 1. Delete any existing OTPs for this user
    db.query(models.PasswordResetOTP).filter(
        models.PasswordResetOTP.user_id == user.id
    ).delete()

    expires = datetime.datetime.now(timezone.utc) + timedelta(minutes=10)
    db_otp = models.PasswordResetOTP(
        id=str(uuid.uuid4()),
        user_id=user.id,
        otp_code=otp_code,
        expires_at=expires
    )
    db.add(db_otp)
    db.commit()
    db.refresh(db_otp)
    return db_otp



def get_valid_otp(db: Session, email: str, otp_code: str) -> Optional[models.PasswordResetOTP]:
    now = datetime.datetime.now(timezone.utc)
    db_user = get_user_by_email(db, email=email)
    if not db_user:
        return None

    db_otp = db.query(models.PasswordResetOTP).filter(
        models.PasswordResetOTP.user_id == db_user.id,
        models.PasswordResetOTP.otp_code == otp_code,
        models.PasswordResetOTP.expires_at > now
    ).first()
    
    return db_otp


def update_user_password(db: Session, user: models.User, new_password: str) -> models.User:
    user.password_hash = auth_service.get_password_hash(new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def delete_otp(db: Session, db_otp: models.PasswordResetOTP):
    db.delete(db_otp)
    db.commit()


def get_all_template_names(db: Session) -> List[str]:
    templates = db.query(models.WorkoutTemplate.template_name).order_by(models.WorkoutTemplate.template_name).all()
    # The result is a list of tuples, e.g., [('Chest Day',), ('Leg Day',)], extract the names
    return [name for name, in templates]

def get_template_by_name(db: Session, template_name: str) -> Optional[models.WorkoutTemplate]:
    return db.query(models.WorkoutTemplate).filter(models.WorkoutTemplate.template_name == template_name).first()


def create_template(db: Session, template_name: str, exercise_names: List[str]) -> models.WorkoutTemplate:
    db_template = models.WorkoutTemplate(
        id=str(uuid.uuid4()),
        template_name=template_name,
        exercise_names=exercise_names
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def log_app_metric(db: Session, user_id: str):
    try:
        # Try to find an existing record for this user
        metric = db.query(models.AppMetric).filter(models.AppMetric.user_id == user_id).first()
        
        if metric:
            # Update existing record
            metric.last_app_query = datetime.datetime.utcnow()
            # --- NEW: Increment counter ---
            metric.total_api_calls += 1
        else:
            # Create new record
            metric = models.AppMetric(
                id=str(uuid.uuid4()),
                user_id=user_id,
                last_app_query=datetime.datetime.utcnow(),
                # --- NEW: Initialize counter ---
                total_api_calls=1 
            )
            db.add(metric)
        
        db.commit()
        db.refresh(metric)
        return metric
    except Exception as e:
        db.rollback()
        print(f"Error logging app metric for user {user_id}: {e}")
        # Do not raise, we don't want metrics logging to break the request
        return None
    

def log_rubbish_voice_log(db: Session, user_id: str):
    try:
        # Try to find an existing record for this user
        metric = db.query(models.AppMetric).filter(models.AppMetric.user_id == user_id).first()
        
        if metric.rubbish_voice_logs:
            metric.rubbish_voice_logs += 1
        else:
            metric.rubbish_voice_logs = 1
        
        db.commit()
        db.refresh(metric)
        return metric
    except Exception as e:
        db.rollback()
        print(f"Error logging app metric for user {user_id}: {e}")
        # Do not raise, we don't want metrics logging to break the request
        return None

def log_open_ai_query(db: Session, user_id: str):
    print("adding to log metric")
    try:
        # Try to find an existing record for this user
        metric = db.query(models.AppMetric).filter(models.AppMetric.user_id == user_id).first()
        
        if metric.open_ai_calls:
            metric.open_ai_calls +=1
        else:
            metric.open_ai_calls = 1
        
        db.commit()
        db.refresh(metric)
        return metric
    except Exception as e:
        db.rollback()
        print(f"Error logging app metric for user {user_id}: {e}")
        # Do not raise, we don't want metrics logging to break the request
        return None


def get_friendship_status(db: Session, user_a: str, user_b: str) -> str:
    """
    Returns: 'none', 'pending_sent', 'pending_received', 'accepted'
    """
    # Check if A sent to B
    sent = db.query(models.Friendship).filter(
        models.Friendship.requester_id == user_a,
        models.Friendship.addressee_id == user_b
    ).first()
    
    if sent:
        if sent.status == 'accepted': return 'accepted'
        return 'pending_sent'
        
    # Check if B sent to A
    received = db.query(models.Friendship).filter(
        models.Friendship.requester_id == user_b,
        models.Friendship.addressee_id == user_a
    ).first()
    
    if received:
        if received.status == 'accepted': return 'accepted'
        return 'pending_received'
        
    return 'none'

def send_friend_request(db: Session, requester_id: str, addressee_id: str):
    # Check existing
    existing = db.query(models.Friendship).filter(
        or_(
            and_(models.Friendship.requester_id == requester_id, models.Friendship.addressee_id == addressee_id),
            and_(models.Friendship.requester_id == addressee_id, models.Friendship.addressee_id == requester_id)
        )
    ).first()
    
    if existing:
        return existing

    friendship = models.Friendship(
        id=str(uuid.uuid4()),
        requester_id=requester_id,
        addressee_id=addressee_id,
        status="pending"
    )
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return friendship


def respond_to_friend_request(db: Session, user_id: str, friendship_id: str, action: str):
    # User must be the addressee to accept
    friendship = db.query(models.Friendship).filter(models.Friendship.id == friendship_id).first()
    
    if not friendship:
        return None
        
    if friendship.addressee_id != user_id:
        return None # Unauthorized
        
    if action == 'accept':
        friendship.status = 'accepted'
    elif action == 'reject':
        db.delete(friendship) # Or set to 'rejected'
        
    db.commit()
    return friendship

def get_friends(db: Session, user_id: str):
    """Get all accepted friendships"""
    # Query friendships where user is either requester or addressee AND status is accepted
    friendships = db.query(models.Friendship).filter(
        and_(
            or_(models.Friendship.requester_id == user_id, models.Friendship.addressee_id == user_id),
            models.Friendship.status == 'accepted'
        )
    ).all()
    
    friend_ids = []
    for f in friendships:
        if f.requester_id == user_id:
            friend_ids.append(f.addressee_id)
        else:
            friend_ids.append(f.requester_id)
            
    return db.query(models.User).filter(models.User.id.in_(friend_ids)).all()

def search_users(db: Session, query: str, current_user_id: str):
    """Search users by name/email, excluding self"""
    search = f"%{query}%"
    return db.query(models.User).filter(
        and_(
            models.User.id != current_user_id,
            or_(
                models.User.first_name.ilike(search),
                models.User.last_name.ilike(search),
                models.User.email.ilike(search)
            )
        )
    ).limit(20).all()

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
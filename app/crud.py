from sqlalchemy.orm import Session
import uuid
from . import models, schemas
from .services.ai_service import WorkoutLog
from app.auth import auth_service
from datetime import timezone, timedelta
import datetime
from typing import Optional

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

    # Mark the workout object as modified in the session
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
                # No need to add to incoming_set_ids as new sets don't exist in current_sets_db
            # else: (Case where ID is provided but doesn't exist - ignore or raise error if needed)
            #    pass

        # --- DELETE sets that are in the DB but were NOT in the incoming payload ---
        set_ids_to_delete = current_sets_db.keys() - incoming_set_ids
        for set_id in set_ids_to_delete:
            db.delete(current_sets_db[set_id])

    try:
        db.commit()
        db.refresh(db_workout) # Refresh to load relationships correctly
        return db_workout
    except Exception as e:
        db.rollback() # Rollback in case of error during commit
        print(f"Error updating workout: {e}") # Or use logger
        raise e # Re-raise the exception to be handled by the endpoint

def create_workout_from_log(db: Session, log: WorkoutLog, user_id: str, created_at: Optional[datetime.datetime] = None) -> models.Workout:

    workout_timestamp = created_at if created_at else datetime.datetime.now(datetime.timezone.utc)

    db_workout = models.Workout(
        id=str(uuid.uuid4()),
        user_id=user_id,
        notes=log.note,
        workout_type=log.workout_type,
        created_at=workout_timestamp
    )
    db.add(db_workout)
    db.commit()
    db.refresh(db_workout)

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

    db.commit()
    return db_workout

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

    # 1. Delete all child exercise sets linked to this workout
    # We do this first to satisfy the foreign key constraint
    db.query(models.ExerciseSet).filter(
        models.ExerciseSet.workout_id == workout_id
    ).delete(synchronize_session=False)

    # 2. Now, delete the workout itself
    db.delete(db_workout)
    
    # 3. Commit the transaction
    db.commit()
    
    return db_workout


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
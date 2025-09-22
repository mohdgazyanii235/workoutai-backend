# app/crud.py
from sqlalchemy.orm import Session
import uuid
from . import models, schemas
from .services.ai_service import WorkoutLog
from app.auth import auth_service
import datetime

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




def create_workout_from_log(db: Session, log: WorkoutLog, user_id: str) -> models.Workout:
    db_workout = models.Workout(
        id=str(uuid.uuid4()),
        user_id=user_id,
        notes=log.note,
        workout_type=log.workout_type
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
from sqlalchemy.orm import Session
import uuid
from . import models, schemas
from .services.ai_service import WorkoutLog, ExerciseSet as AISet
from app.auth import auth_service

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = None
    if user.password:
        hashed_password = auth_service.get_password_hash(user.password)
    db_user = models.User(
        id=str(uuid.uuid4()), 
        email=user.email, 
        password_hash=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- Updated Workout CRUD Function ---
def create_workout_from_log(db: Session, log: WorkoutLog, user_id: str) -> models.Workout:
    db_workout = models.Workout(
        id=str(uuid.uuid4()), 
        user_id=user_id, # Use the real user_id
        notes="Workout logged via voice."
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

def print_workout_log(log: WorkoutLog):
    print("\n--- AI Structured Workout Log ---")
    for i, ai_set in enumerate(log.sets):
        print(f"  Set {i + 1}:")
        print(f"    Exercise: {ai_set.exercise_name}")
        print(f"    Reps: {ai_set.reps}")
        print(f"    Weight: {ai_set.weight} {ai_set.weight_unit}")
        print(f"    Sets: {ai_set.sets}")
    print("---------------------------------\n")
    # Return a temporary Workout object to satisfy the router's response model
    return models.Workout(id="test_id_123", notes="Log printed to console.")
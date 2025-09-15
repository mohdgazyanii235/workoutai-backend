from sqlalchemy.orm import Session
import uuid
from . import models, schemas
from .services.ai_service import WorkoutLog, ExerciseSet as AISet # Import the AI data models

def create_workout_from_log(db: Session, log: WorkoutLog) -> models.Workout:
    # For now, we'll use a placeholder user_id. We'll replace this with real
    # authentication later.
    placeholder_user_id = "user_placeholder_123"

    # Create the main Workout entry
    db_workout = models.Workout(
        id=str(uuid.uuid4()), 
        user_id=placeholder_user_id,
        notes="Workout logged via voice."
    )
    db.add(db_workout)
    db.commit()
    db.refresh(db_workout)

    # For each set identified by the AI, create an ExerciseSet entry
    for i, ai_set in enumerate(log.sets):
        db_exercise_set = models.ExerciseSet(
            id=str(uuid.uuid4()),
            exercise_name=ai_set.exercise_name,
            set_number=i + 1,
            reps=ai_set.reps,
            weight=ai_set.weight,
            weight_unit=ai_set.weight_unit,
            workout_id=db_workout.id
        )
        db.add(db_exercise_set)
    
    db.commit()
    return db_workout
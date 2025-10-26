# seed.py
import uuid
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models, crud # <-- Import crud
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEMPLATE_DATA = [
    {"name": "Chest", "exercises": ["Bench Press", "Incline Dumbbell Press", "Dips", "Cable Flyes"]},
    {"name": "Shoulders", "exercises": ["Overhead Press", "Lateral Raises", "Front Raises", "Dips"]},
    {"name": "Legs", "exercises": ["Squat", "Leg Press", "Leg Curls", "Leg Extensions"]},
    {"name": "Back & Biceps", "exercises": ["Pull-ups", "Lat Pulldown", "Bent-over Rows", "Bicep Curls"]},
    {"name": "Push", "exercises": ["Bench Press", "Overhead Press", "Incline Dumbbell Press", "Lateral Raises", "Tricep Pushdown", "Dips"]},
    {"name": "Pull", "exercises": ["Pull-ups", "Bent-over Rows", "Lat Pulldown", "Bicep Curls"]},
    {"name": "Full Body", "exercises": ["Squat", "Bench Press", "Bent-over Rows"]},
    {"name": "Arms", "exercises": ["Bicep Curls", "Tricep Pushdown", "Dips"]},

]


def seed_data(db: Session):
    logger.info("Seeding workout templates...")

    existing_templates = db.query(models.WorkoutTemplate).all()
    existing_template_names = {t.template_name for t in existing_templates}

    template_count = 0
    for template_data in TEMPLATE_DATA:
        if template_data["name"] not in existing_template_names:
            try:
                crud.create_template( # Use the crud function
                    db=db,
                    template_name=template_data["name"],
                    exercise_names=template_data["exercises"]
                )
                template_count += 1
                logger.info(f"Added Template: {template_data['name']}")
            except Exception as e:
                 logger.error(f"Failed to add template {template_data['name']}: {e}")
                 db.rollback() # Rollback on error for this specific template
        else:
            logger.info(f"Skipped Template (already exists): {template_data['name']}")

    logger.info(f"Template seeding complete. Added {template_count} new templates.")

if __name__ == "__main__":
    logger.info("Application starting up... creating tables if they don't exist.")
    # Create all tables defined in models.py
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_data(db)
    except Exception as e:
        logger.error(f"An error occurred during seeding: {e}")
    finally:
        db.close()
        logger.info("Database session closed.")
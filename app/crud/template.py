from sqlalchemy.orm import Session
from app import models
from typing import List, Optional
import uuid

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
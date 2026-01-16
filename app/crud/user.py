from sqlalchemy.orm import Session
from app import models
from app.schemas import user as user_schemas
import uuid
from app.auth import auth_service
import datetime

def get_user(db: Session, id: str):
    return db.query(models.User).filter(models.User.id == id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: user_schemas.UserCreate):
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

def update_user_profile(db: Session, user_id: str, update: user_schemas.UserUpdate):
    db_user = get_user(db, id=user_id)
    if not db_user:
        return None

    update_data = update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field in ["weight", "fat_percentage", "deadlift_1rm", "squat_1rm", "bench_1rm"] and value:
            # ... existing complex array handling ...
            current = getattr(db_user, field) or []
            normalized = []
            for entry in value:
                if hasattr(entry, "model_dump"):
                    data = entry.model_dump()
                else:
                    data = dict(entry)
                if isinstance(data.get("date"), (datetime.date, datetime.datetime)):
                    data["date"] = data["date"].isoformat()
                normalized.append(data)
            current.extend(normalized)
            setattr(db_user, field, current)
        else:
            setattr(db_user, field, value)

    db_user.is_onboarded = True
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_location(db: Session, user_id: str, lat: float, long: float):
    """Updates user's lat/long for discovery features"""
    db_user = get_user(db, id=user_id)
    if db_user:
        db_user.latitude = lat
        db_user.longitude = long
        db_user.last_location_update = datetime.datetime.utcnow()
        db.commit()
    return db_user


def update_history_tracked_field(db, db_user, updated_value: float, date_str: str, field_type: str):
    new_entry = {"date": date_str, "value": updated_value}
    current_history = getattr(db_user, field_type) or []
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

def get_all_users_lite(db: Session):
    return db.query(models.User).order_by(models.User.email).all()

def get_total_user_count(db: Session) -> int:
    """Count total number of registered users"""
    return db.query(models.User).count()
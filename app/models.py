# app/models.py
import datetime
from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey, Boolean, Date, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .database import Base

class Friendship(Base):
    __tablename__ = 'friendships'
    
    id = Column(String, primary_key=True, index=True)
    requester_id = Column(String, ForeignKey('users.id'), nullable=False)
    addressee_id = Column(String, ForeignKey('users.id'), nullable=False)
    status = Column(String, default="pending", nullable=False) # "pending", "accepted", "blocked"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# --- NEW: Close Friends Association Table ---
class CloseFriend(Base):
    __tablename__ = 'close_friends'
    
    # The user who owns the list
    owner_id = Column(String, ForeignKey('users.id'), nullable=False)
    # The friend they marked as "close"
    friend_id = Column(String, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint('owner_id', 'friend_id'),
    )
# --------------------------------------------

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Profile fields
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)

    bio = Column(String, nullable=True)
    profile_photo_url = Column(String, nullable=True)

    # Strenght Information
    weight = Column(JSON, default=list, nullable=True)
    height = Column(Float, nullable=True)
    fat_percentage = Column(JSON, default=list, nullable=True)
    deadlift_1rm = Column(JSON, default=list, nullable=True)
    squat_1rm = Column(JSON, default=list, nullable=True)
    bench_1rm = Column(JSON, default=list, nullable=True)

    # Goals
    goal_weight = Column(Float, nullable=True)
    goal_fat_percentage = Column(Float, nullable=True)
    goal_deadlift_1rm = Column(Float, nullable=True)
    goal_squat_1rm = Column(Float, nullable=True)
    goal_bench_1rm = Column(Float, nullable=True)

    is_onboarded = Column(Boolean, nullable=False, default=False)
    workouts = relationship("Workout", back_populates="user")
    app_metric = relationship("AppMetric", back_populates="user", uselist=False)

    notifications_received = relationship("Notification", foreign_keys="Notification.recipient_id", back_populates="recipient")
    notifications_sent = relationship("Notification", foreign_keys="Notification.sender_id", back_populates="sender")

    # --- NEW: Relationship for Close Friends ---
    # This allows us to easily query "who has this user marked as a close friend?"
    close_friends = relationship("CloseFriend", foreign_keys=[CloseFriend.owner_id], backref="owner", cascade="all, delete-orphan")

    nudge_count = Column(Integer, default=0, nullable=False)
    spot_count = Column(Integer, default=0, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

class Workout(Base):
    __tablename__ = 'workouts'
    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    notes = Column(String, nullable=True)
    workout_type = Column(String, nullable=True)
    user_id = Column(String, ForeignKey('users.id'))
    user = relationship("User", back_populates="workouts")
    visibility = Column(String, default="public", nullable=False)
    sets = relationship(
        "ExerciseSet", 
        back_populates="workout", 
        cascade="all, delete-orphan"
    )
    cardio_sessions = relationship(
        "CardioSession", 
        back_populates="workout", 
        cascade="all, delete-orphan"
    )

class ExerciseSet(Base):
    __tablename__ = 'exercise_sets'
    id = Column(String, primary_key=True, index=True)
    exercise_name = Column(String, nullable=False)
    set_number = Column(Integer, nullable=False)
    reps = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    weight_unit = Column(String, default='kg')
    workout_id = Column(String, ForeignKey('workouts.id'))
    workout = relationship("Workout", back_populates="sets")


class CardioSession(Base):
    __tablename__ = 'cardio_sessions'
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False) # e.g., "Running", "Rowing"
    
    # We will store duration in minutes for consistency
    duration_minutes = Column(Float, nullable=True) 
    
    distance = Column(Float, nullable=True) 
    distance_unit = Column(String, nullable=True) # e.g., "km", "miles"
    
    speed = Column(Float, nullable=True)
    pace = Column(String, nullable=True)
    pace_unit = Column(String, nullable=True) # e.g., "Min/KM", "Min/Mile"
    laps = Column(Integer, nullable=True)
    
    workout_id = Column(String, ForeignKey('workouts.id'))
    workout = relationship("Workout", back_populates="cardio_sessions")


class PasswordResetOTP(Base):
    __tablename__ = 'password_reset_otps'
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    otp_code = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    user = relationship("User")

class WorkoutTemplate(Base):
    __tablename__ = 'workout_templates'
    id = Column(String, primary_key=True, index=True)
    template_name = Column(String, nullable=False, unique=True, index=True)
    # Store list of exercise names directly
    exercise_names = Column(JSON, nullable=False, default=list)


class AppMetric(Base):
    __tablename__ = 'app_metrics'
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey('users.id'), unique=True, nullable=False)
    last_app_query = Column(DateTime, default=datetime.datetime.utcnow)
    total_api_calls = Column(Integer, default=0, nullable=True)
    user = relationship("User", back_populates="app_metric")
    open_ai_calls = Column(Integer, default=0, nullable=True)
    rubbish_voice_logs = Column(Integer, default=0, nullable=True)


class Notification(Base):
    __tablename__ = 'notifications'
    
    id = Column(String, primary_key=True, index=True)
    recipient_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    sender_id = Column(String, ForeignKey('users.id'), nullable=True) # Nullable for system messages
    
    type = Column(String, nullable=False) # 'FRIEND_REQUEST', 'WORKOUT_SHARE', 'SYSTEM'
    reference_id = Column(String, nullable=True) # ID of the related object (e.g., friendship_id, workout_id)
    
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="notifications_received")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="notifications_sent")


class UserInteraction(Base):
    __tablename__ = 'user_interactions'
    id = Column(String, primary_key=True, index=True)
    sender_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    recipient_id = Column(String, ForeignKey('users.id'), nullable=False)
    action_type = Column(String, nullable=False) # 'nudge' or 'spot'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
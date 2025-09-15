# app/models.py
import datetime
from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    workouts = relationship("Workout", back_populates="user")

class Workout(Base):
    __tablename__ = 'workouts'
    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(String, nullable=True)
    user_id = Column(String, ForeignKey('users.id'))
    user = relationship("User", back_populates="workouts")
    sets = relationship("ExerciseSet", back_populates="workout")

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
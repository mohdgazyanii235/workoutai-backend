from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import SessionLocal
from app import models
from app.crud import notification as crud_notification
import datetime
import logging

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

def check_scheduled_workouts():
    """
    Runs daily. Finds all workouts scheduled for 'today' that are 'planned'.
    Sends a push notification to the owner.
    """
    db = SessionLocal()
    try:
        today = datetime.date.today()
        logger.info(f"Running scheduled workout check for date: {today}")
        
        # Find planned workouts for today
        # Note: created_at stores the scheduled date for planned workouts
        # We need to cast the DateTime to a Date for comparison
        workouts = db.query(models.Workout).filter(
            models.Workout.status == "planned",
            # SQLAlchemy func.date() handles the casting
            func.date(models.Workout.created_at) == today 
        ).all()

        logger.info(f"Found {len(workouts)} planned workouts for today.")

        for workout in workouts:
            title = "Workout Reminder 📅"
            workout_type = workout.workout_type or 'workout'
            message = f"You planned a {workout_type} for today. Time to crush it!"
            
            # Send notification using existing CRUD
            # We use type="SYSTEM" or "REMINDER" to differentiate
            crud_notification.create_notification(
                db=db,
                recipient_id=workout.user_id,
                type="REMINDER", 
                title=title,
                message=message,
                reference_id=workout.id
            )
            
            logger.info(f"Sent reminder for workout {workout.id} to user {workout.user_id}")
            
            # Optional: We could update a flag here to say 'notified' if we wanted to be idempotent 
            # within the same day, but relying on the scheduler running once per day is standard.

    except Exception as e:
        logger.error(f"Scheduler Error in check_scheduled_workouts: {e}")
    finally:
        db.close()

def auto_complete_planned_workouts():
    """
    Runs at the end of the day (e.g., 23:59).
    Finds all 'planned' workouts for 'today' and marks them as 'completed'.
    This assumes positive intent: if they planned it, they did it.
    """
    db = SessionLocal()
    try:
        today = datetime.date.today()
        logger.info(f"Running auto-complete check for date: {today}")

        # Find planned workouts for today
        workouts = db.query(models.Workout).filter(
            models.Workout.status == "planned",
            func.date(models.Workout.created_at) == today
        ).all()

        count = 0
        for workout in workouts:
            workout.status = "completed"
            db.add(workout)
            count += 1
        
        if count > 0:
            db.commit()
            logger.info(f"Auto-completed {count} workouts for {today}")
        else:
            logger.info(f"No planned workouts to auto-complete for {today}")

    except Exception as e:
        logger.error(f"Scheduler Error in auto_complete_planned_workouts: {e}")
        db.rollback()
    finally:
        db.close()

def start_scheduler():
    # 1. Morning Reminder: Run every day at 8:00 AM server time
    scheduler.add_job(check_scheduled_workouts, 'cron', hour=8, minute=0)
    
    # 2. End-of-Day Auto-Complete: Run every day at 11:59 PM server time
    scheduler.add_job(auto_complete_planned_workouts, 'cron', hour=23, minute=59)

    # For testing purposes, you might want to uncomment this to run every minute:
    # scheduler.add_job(check_scheduled_workouts, 'interval', minutes=1)
    
    scheduler.start()
    logger.info("Background Scheduler started.")
from sqlalchemy.orm import Session
from app import models
import uuid
import datetime

def log_app_metric(db: Session, user_id: str):
    try:
        metric = db.query(models.AppMetric).filter(models.AppMetric.user_id == user_id).first()
        
        if metric:
            metric.last_app_query = datetime.datetime.utcnow()
            metric.total_api_calls += 1
        else:
            metric = models.AppMetric(
                id=str(uuid.uuid4()),
                user_id=user_id,
                last_app_query=datetime.datetime.utcnow(),
                total_api_calls=1 
            )
            db.add(metric)
        
        db.commit()
        db.refresh(metric)
        return metric
    except Exception as e:
        db.rollback()
        print(f"Error logging app metric for user {user_id}: {e}")
        return None
    

def log_rubbish_voice_log(db: Session, user_id: str):
    try:
        metric = db.query(models.AppMetric).filter(models.AppMetric.user_id == user_id).first()
        
        if metric.rubbish_voice_logs:
            metric.rubbish_voice_logs += 1
        else:
            metric.rubbish_voice_logs = 1
        
        db.commit()
        db.refresh(metric)
        return metric
    except Exception as e:
        db.rollback()
        print(f"Error logging app metric for user {user_id}: {e}")
        return None

def log_open_ai_query(db: Session, user_id: str):
    print("adding to log metric")
    try:
        metric = db.query(models.AppMetric).filter(models.AppMetric.user_id == user_id).first()
        
        if metric.open_ai_calls:
            metric.open_ai_calls +=1
        else:
            metric.open_ai_calls = 1
        
        db.commit()
        db.refresh(metric)
        return metric
    except Exception as e:
        db.rollback()
        print(f"Error logging app metric for user {user_id}: {e}")
        return None

def get_all_app_metrics(db: Session):
    """Fetch all metrics joined with user email for context"""
    return db.query(models.AppMetric, models.User.email).join(models.User, models.AppMetric.user_id == models.User.id).all()
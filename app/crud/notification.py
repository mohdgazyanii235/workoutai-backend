from sqlalchemy.orm import Session
from app import models
import uuid
import requests
from typing import Optional

NATIVE_NOTFIY_APP_ID = 32792
NATIVE_NOTIFY_APP_TOKEN = 'ssPq3VWQFV50vo8zLTTpOO'

def send_push_notification(target_users: list, title: str, message: str):
    """
    Sends the actual push notification via NativeNotify.
    """
    print(f"Sending Push to {target_users}: {title}")
    notification_url = 'https://app.nativenotify.com/api/indie/group/notification'
    payload = {
        'subIDs': target_users,
        'appId': NATIVE_NOTFIY_APP_ID,
        'appToken': NATIVE_NOTIFY_APP_TOKEN,
        'title': title,
        'message': message
    }

    try:
        response = requests.post(notification_url, json=payload)
        # print(response.text)
    except Exception as e:
        print(f"Failed to send push: {e}")

def create_notification(
    db: Session, 
    recipient_id: str, 
    type: str, 
    title: str, 
    message: str, 
    sender_id: Optional[str] = None, 
    reference_id: Optional[str] = None
):
    """
    Creates a persistent notification in the DB and triggers a push.
    """
    # 1. Create DB Record
    db_notif = models.Notification(
        id=str(uuid.uuid4()),
        recipient_id=recipient_id,
        sender_id=sender_id,
        type=type,
        reference_id=reference_id,
        title=title,
        message=message,
        is_read=False
    )
    db.add(db_notif)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving notification to DB: {e}")

    # 2. Trigger Push
    send_push_notification([recipient_id], title, message)
    
    return db_notif

def get_notifications(db: Session, user_id: str, limit: int = 50, skip: int = 0):
    return db.query(models.Notification).filter(
        models.Notification.recipient_id == user_id
    ).order_by(models.Notification.created_at.desc()).offset(skip).limit(limit).all()

def mark_notification_read(db: Session, notification_id: str, user_id: str):
    notif = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.recipient_id == user_id
    ).first()
    
    if notif:
        notif.is_read = True
        db.commit()
        db.refresh(notif)
    return notif

def mark_all_notifications_read(db: Session, user_id: str):
    db.query(models.Notification).filter(
        models.Notification.recipient_id == user_id,
        models.Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
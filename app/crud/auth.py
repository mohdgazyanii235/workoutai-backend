from sqlalchemy.orm import Session
from app import models
import uuid
import datetime
from datetime import timezone, timedelta
from typing import Optional
from app.auth import auth_service
from . import user as crud_user

def create_reset_otp(db: Session, user: models.User, otp_code: str) -> models.PasswordResetOTP:
    # 1. Delete any existing OTPs for this user
    db.query(models.PasswordResetOTP).filter(
        models.PasswordResetOTP.user_id == user.id
    ).delete()

    expires = datetime.datetime.now(timezone.utc) + timedelta(minutes=10)
    db_otp = models.PasswordResetOTP(
        id=str(uuid.uuid4()),
        user_id=user.id,
        otp_code=otp_code,
        expires_at=expires
    )
    db.add(db_otp)
    db.commit()
    db.refresh(db_otp)
    return db_otp

def get_valid_otp(db: Session, email: str, otp_code: str) -> Optional[models.PasswordResetOTP]:
    now = datetime.datetime.now(timezone.utc)
    db_user = crud_user.get_user_by_email(db, email=email)
    if not db_user:
        return None

    db_otp = db.query(models.PasswordResetOTP).filter(
        models.PasswordResetOTP.user_id == db_user.id,
        models.PasswordResetOTP.otp_code == otp_code,
        models.PasswordResetOTP.expires_at > now
    ).first()
    
    return db_otp

def update_user_password(db: Session, user: models.User, new_password: str) -> models.User:
    user.password_hash = auth_service.get_password_hash(new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def delete_otp(db: Session, db_otp: models.PasswordResetOTP):
    db.delete(db_otp)
    db.commit()
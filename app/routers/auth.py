from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated
from app.database import get_db
from app.auth import auth_service
from app.security.security import get_api_key
import random
import logging

from app.schemas import user as user_schemas
from app.schemas import auth as auth_schemas
from app.crud import user as user_crud
from app.crud import auth as auth_crud

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(get_api_key)])

@router.post("/signup", response_model=user_schemas.User)
def signup(user: user_schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = user_crud.get_user_by_email(db, email=user.email)
    if db_user:
        print("Email Already Registered.")
        raise HTTPException(status_code=400, detail="Email already registered")
    return user_crud.create_user(db=db, user=user)

@router.post("/token", response_model=auth_schemas.Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], 
    db: Session = Depends(get_db)
):
    user = user_crud.get_user_by_email(db, email=form_data.username)
    if not user or not user.password_hash or not auth_service.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_service.create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/request-otp")
def request_password_reset(
    request_data: auth_schemas.ForgotPasswordRequest, 
    db: Session = Depends(get_db)
):
    """
    User requests a password reset.
    """
    db_user = user_crud.get_user_by_email(db, email=request_data.email)
    
    if db_user:
        otp_code = str(random.randint(100000, 999999))
        auth_crud.create_reset_otp(db, user=db_user, otp_code=otp_code)
        
        # Send email will go here!
        logging.info(f"OTP for {db_user.email}: {otp_code}")

    # Always return a generic success message for security
    return {"message": "If an account with this email exists, an OTP has been sent."}

@router.post("/verify-otp")
def verify_reset_otp(
    request_data: auth_schemas.VerifyOTPRequest, 
    db: Session = Depends(get_db)
):
    """
    User submits the OTP to verify it's valid before proceeding.
    """
    db_otp = auth_crud.get_valid_otp(
        db, 
        email=request_data.email, 
        otp_code=request_data.otp
    )
    
    if not db_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid or expired OTP."
        )
        
    return {"message": "OTP verified successfully."}

@router.post("/reset-password")
def reset_password_with_otp(
    request_data: auth_schemas.ResetPasswordRequest, 
    db: Session = Depends(get_db)
):
    """
    User submits the OTP *and* new password to finalize the reset.
    """
    # 1. Verify the OTP is valid (re-verification step)
    db_otp = auth_crud.get_valid_otp(
        db, 
        email=request_data.email, 
        otp_code=request_data.otp
    )
    
    if not db_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid or expired OTP."
        )
        
    # 2. Update the user's password
    auth_crud.update_user_password(
        db, 
        user=db_otp.user, 
        new_password=request_data.new_password
    )
    
    # 3. Delete the used OTP
    auth_crud.delete_otp(db, db_otp=db_otp)
    
    return {"message": "Password has been reset successfully."}
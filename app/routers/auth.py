from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated
from app import schemas, crud
from app.database import get_db
from app.auth import auth_service
from app.security.security import get_api_key
import time # Import the time module

router = APIRouter(prefix="/auth", tags=["auth"])

# --- Your existing /signup and /token endpoints ---
@router.post("/signup", response_model=schemas.User)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        print("Email Already Registered.")
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], 
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_email(db, email=form_data.username)
    # Important: Check if the user has a password before verifying
    if not user or not user.password_hash or not auth_service.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_service.create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Could not validate Google credentials: {e}")

    user_info = token.get('userinfo')
    if not user_info or not user_info.get('email'):
        raise HTTPException(status_code=400, detail="Could not retrieve user info from Google")

    db_user = crud.get_user_by_email(db, email=user_info['email'])
    
    if not db_user:
        # ** THE FIX IS HERE: Create a placeholder password from a timestamp **
        placeholder_password = str(time.time())
        new_user_data = schemas.UserCreate(email=user_info['email'], password=placeholder_password)
        db_user = crud.create_user(db=db, user=new_user_data)
        
    access_token = auth_service.create_access_token(data={"sub": db_user.id})
    
    return {"access_token": access_token, "token_type": "bearer"}
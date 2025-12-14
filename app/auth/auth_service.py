from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional, TypedDict
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app import models
from app.schemas import user as user_schemas
from app.crud import user as user_crud
from app.database import get_db

SECRET_KEY: str = os.getenv("SECRET_KEY")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 52560000

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return _pwd_context.hash(password)

class JWTPayload(TypedDict, total=False):
    sub: str
    exp: int

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def create_access_token(data: dict) -> str:
    to_encode: JWTPayload = JWTPayload(**data)
    expire = _utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = int(expire.timestamp())
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> JWTPayload:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload

def _resolve_db_user(db: Session, user_id: str) -> models.User | None:
    return user_crud.get_user(db, id=user_id)

def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> user_schemas.User:
    try:
        payload = decode_token(token)
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            raise _credentials_exception()
    except JWTError:
        raise _credentials_exception()

    db_user = _resolve_db_user(db, user_id)
    if db_user is None:
        raise _credentials_exception()

    return user_schemas.User.model_validate(db_user, from_attributes=True)
# app/auth/auth_service.py
"""
Auth core: hashing utilities, JWT creation/validation, and the FastAPI dependency
that resolves the current user. Designed to be framework-agnostic and easy to test.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional, TypedDict

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db

# ------------------------------------------------------------------------------
# Configuration / Constants
# ------------------------------------------------------------------------------

# NOTE: Use a strong, unique SECRET_KEY in production. Prefer loading from env.
SECRET_KEY: str = os.getenv("SECRET_KEY", "a_super_secret_dev_key")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

# This matches your /auth router's token endpoint (prefix=/auth)
# so OAuth2 clients know where to fetch tokens from.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# ------------------------------------------------------------------------------
# Password Hashing
# ------------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return _pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return _pwd_context.hash(password)


# ------------------------------------------------------------------------------
# JWT Helpers
# ------------------------------------------------------------------------------

class JWTPayload(TypedDict, total=False):
    sub: str             # user id
    exp: int             # epoch seconds (set by us)
    # add custom fields here if needed (e.g. "role": "admin")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(data: dict) -> str:
    """
    Create a short-lived JWT access token.

    The caller typically passes {"sub": <user_id>}. We append an "exp" claim.
    """
    to_encode: JWTPayload = JWTPayload(**data)  # type: ignore[arg-type]
    expire = _utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = int(expire.timestamp())
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> JWTPayload:
    """
    Decode and validate a JWT, raising JWTError on failure.
    Returns the payload if valid.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    # jose validates "exp" automatically; if expired it raises JWTError.
    return payload  # type: ignore[return-value]


# ------------------------------------------------------------------------------
# Current User Dependency
# ------------------------------------------------------------------------------

def _resolve_db_user(db: Session, user_id: str) -> models.User | None:
    """
    Internal helper to fetch a DB user by id.
    IMPORTANT: your CRUD expects the keyword 'id' (not 'user_id').
    """
    # See definition in app/crud.py: def get_user(db: Session, id: str) -> models.User | None
    # We must pass id=..., not user_id=...
    return crud.get_user(db, id=user_id)  # 


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> schemas.User:
    """
    Resolve the current authenticated user from the Bearer token.

    Returns a Pydantic schema (schemas.User) because downstream routers
    type-annotate against schemas, e.g. /log/voice depends on schemas.User.
    """
    try:
        payload = decode_token(token)
        user_id: Optional[str] = payload.get("sub")  # type: ignore[assignment]
        if not user_id:
            raise _credentials_exception()
    except JWTError:
        # Includes expired token, invalid signature, malformed token, etc.
        raise _credentials_exception()

    db_user = _resolve_db_user(db, user_id)
    if db_user is None:
        raise _credentials_exception()

    # Convert SQLAlchemy model -> Pydantic schema expected by routes
    return schemas.User.model_validate(db_user, from_attributes=True)
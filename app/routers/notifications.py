from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Annotated
from app.database import get_db
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key

from app.schemas import notification as notification_schemas
from app.schemas import user as user_schemas
from app.crud import notification as notification_crud

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_api_key)]
)

@router.get("/", response_model=List[notification_schemas.Notification])
def get_my_notifications(
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    limit: int = 50,
    skip: int = 0
):
    return notification_crud.get_notifications(db, current_user.id, limit=limit, skip=skip)

@router.patch("/{notification_id}/read", response_model=notification_schemas.Notification)
def mark_as_read(
    notification_id: str,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    notif = notification_crud.mark_notification_read(db, notification_id, current_user.id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif

@router.post("/mark-all-read")
def mark_all_as_read(
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    notification_crud.mark_all_notifications_read(db, current_user.id)
    return {"message": "All notifications marked as read"}
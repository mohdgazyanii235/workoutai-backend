from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.security.security import get_api_key, get_current_admin

from app.schemas import admin as admin_schemas
from app.schemas import user as user_schemas
from app.crud import admin as admin_crud
from app.crud import user as user_crud
from app.crud import notification as notification_crud

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_api_key), Depends(get_current_admin)]
)

@router.get("/metrics", response_model=List[admin_schemas.AdminMetricResponse])
def get_metrics(
    db: Session = Depends(get_db),
    admin: user_schemas.User = Depends(get_current_admin)
):
    results = admin_crud.get_all_app_metrics(db)
    return [{"metric": m[0], "user_email": m[1]} for m in results]

@router.get("/stats/users/count", response_model=int)
def get_total_users_count(
    db: Session = Depends(get_db),
    admin: user_schemas.User = Depends(get_current_admin)
):
    return user_crud.get_total_user_count(db)

@router.get("/users", response_model=List[admin_schemas.AdminUserSelect])
def get_users_list(
    db: Session = Depends(get_db),
    admin: user_schemas.User = Depends(get_current_admin)
):
    return user_crud.get_all_users_lite(db)

@router.post("/notify")
def send_admin_notification(
    payload: admin_schemas.AdminNotificationCreate,
    admin: user_schemas.User = Depends(get_current_admin)
):
    notification_crud.send_push_notification(
        payload.target_user_ids, payload.title, payload.message
    )
    return {"message": f"Sent {len(payload.target_user_ids)} notifications"}
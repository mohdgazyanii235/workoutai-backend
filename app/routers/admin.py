from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Annotated
from app import schemas, crud, models
from app.database import get_db

from app.security.security import get_api_key, get_current_admin

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_api_key), Depends(get_current_admin)]
)

@router.get("/metrics", response_model=List[schemas.AdminMetricResponse])
def get_metrics(
    db: Session = Depends(get_db),
    admin: schemas.User = Depends(get_current_admin)
):
    results = crud.get_all_app_metrics(db)
    return [{"metric": m[0], "user_email": m[1]} for m in results]

@router.get("/stats/users/count", response_model=int)
def get_total_users_count(
    db: Session = Depends(get_db),
    admin: schemas.User = Depends(get_current_admin)
):
    return crud.get_total_user_count(db)

@router.get("/users", response_model=List[schemas.AdminUserSelect])
def get_users_list(
    db: Session = Depends(get_db),
    admin: schemas.User = Depends(get_current_admin)
):
    return crud.get_all_users_lite(db)

@router.post("/notify")
def send_admin_notification(
    payload: schemas.AdminNotificationCreate,
    admin: schemas.User = Depends(get_current_admin)
):
    
    crud.send_push_notification(
        payload.target_user_ids, payload.title, payload.message
    )
    
    return {"message": f"Sent {len(payload.target_user_ids)} notifications"}
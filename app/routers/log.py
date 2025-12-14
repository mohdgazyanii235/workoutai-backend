from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Annotated
from app.database import get_db
from app.services import ai_service
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key
from app.services.ai_service import InvalidWorkoutException

from app.schemas import workout as workout_schemas
from app.schemas import user as user_schemas
from app.crud import admin as admin_crud
from app.crud import workout as workout_crud

router = APIRouter(prefix="/log", tags=["log"], dependencies=[Depends(get_api_key)])

@router.post("/voice", response_model=workout_schemas.AILogResponse)
def voice_log(
    log: workout_schemas.VoiceLog,
    current_user: Annotated[user_schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    try:
        raw_text = log.text
        structured_data = ai_service.structured_log_text(raw_text)

        if structured_data:
            admin_crud.log_open_ai_query(db, user_id=current_user.id)
            comment = workout_crud.manage_voice_log(db, structured_data, user_id=current_user.id, created_at=log.created_at)
            return workout_schemas.AILogResponse(comment=comment)

        print(structured_data)
        
        return current_user.id
    except InvalidWorkoutException as e:
        raise HTTPException(status_code=400, detail=str(e))
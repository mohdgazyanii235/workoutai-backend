from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Annotated
from app import schemas, crud
from app.database import get_db
from app.services import ai_service
from app.auth.auth_service import get_current_user
from app.security.security import get_api_key
from app.services.ai_service import InvalidWorkoutException

router = APIRouter(prefix="/log", tags=["log"], dependencies=[Depends(get_api_key)])

# @router.post("/voice/test", response_model=schemas.Workout)
# def create_workout_from_voice(
#     log: schemas.WorkoutLogCreate,
#     current_user: Annotated[schemas.User, Depends(get_current_user)],
#     db: Session = Depends(get_db)
# ):
    
#     try:
#         raw_text = log.text
#         structured_data = ai_service.structure_workout_text(raw_text)

#         if structured_data:
#             workout = crud.create_workout_from_log(db, structured_data, user_id=current_user.id, created_at=log.created_at)
#             return workout
#     except InvalidWorkoutException as e:
#         raise HTTPException(status_code=400, detail=str(e))
    


@router.post("/voice", response_model=schemas.AILogResponse)
def voice_log(
    log: schemas.VoiceLog,
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    try:
        raw_text = log.text
        structured_data = ai_service.structured_log_text(raw_text)

        if structured_data:
            crud.log_open_ai_query(db, user_id=current_user.id)
            return schemas.AILogResponse(comment=crud.manage_voice_log(db, structured_data, user_id=current_user.id, created_at=log.created_at))

        print(structured_data)
        
        return current_user.id
    except InvalidWorkoutException as e:
        raise HTTPException(status_code=400, detail=str(e))
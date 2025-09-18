from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Annotated
from app import schemas, crud
from app.database import get_db
from app.services import ai_service
from app.auth.auth_service import get_current_user

router = APIRouter(prefix="/log", tags=["log"])

@router.post("/voice", response_model=schemas.Workout)
def create_workout_from_voice(
    log: schemas.WorkoutLogCreate, 
    # Reorder the parameters: required ones first, then ones with defaults
    current_user: Annotated[schemas.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    raw_text = log.text
    structured_data = ai_service.structure_workout_text(raw_text)

    if structured_data:
        workout = crud.create_workout_from_log(db, structured_data, user_id=current_user.id)
        return workout
    
    # Handle cases where the AI might fail
    raise HTTPException(status_code=400, detail="Failed to parse workout text.")
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import schemas, crud
from app.database import get_db
from app.services import ai_service

router = APIRouter(
    prefix="/log",
    tags=["log"],
)

@router.post("/voice", response_model=schemas.Workout)
def create_workout_from_voice(log: schemas.WorkoutLogCreate, db: Session = Depends(get_db)):
    # 1. Get the raw text from the request.
    raw_text = log.text
    print(raw_text)

    # 2. Call the AI service to get structured data.
    structured_data = ai_service.structure_workout_text(raw_text)

    # 3. If the AI was successful, save the data to the database using the CRUD function.
    if structured_data:
        workout = crud.create_workout_from_log(db, structured_data)
        return workout
    
    # Handle cases where the AI might fail
    return {"id": "error", "notes": "Failed to parse workout."}
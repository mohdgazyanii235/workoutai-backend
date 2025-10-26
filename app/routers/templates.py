# app/routers/templates.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import schemas, crud
from app.database import get_db
from app.security.security import get_api_key

router = APIRouter(
    # Changed prefix to /templates
    prefix="/templates",
    tags=["templates"],
    dependencies=[Depends(get_api_key)]
)

@router.get("/suggestions", response_model=List[str])
def get_template_name_suggestions(
    query: str = "", # The user's typed text
    db: Session = Depends(get_db)
):
    all_names = crud.get_all_template_names(db) #

    if not query:
        return all_names # Return all if query is empty

    # Filter in Python (case-insensitive)
    suggestions = [
        name for name in all_names
        if query.lower() in name.lower()
    ]
    return suggestions

@router.get("/", response_model=List[str]) # Use root path, return list of names
def get_workout_template_exercises(
    template_name: str, # Changed parameter name to match common practice
    db: Session = Depends(get_db)
):

    template = crud.get_template_by_name(db, template_name=template_name) #
    if not template or not template.exercise_names: # Check template exists and has names
        # Return empty list instead of 404 to simplify frontend logic
        return []
    # Return the list of exercise names directly
    return template.exercise_names #
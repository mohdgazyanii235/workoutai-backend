from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.security.security import get_api_key
from app.crud import template as template_crud

router = APIRouter(
    prefix="/templates",
    tags=["templates"],
    dependencies=[Depends(get_api_key)]
)

@router.get("/suggestions", response_model=List[str])
def get_template_name_suggestions(
    query: str = "",
    db: Session = Depends(get_db)
):
    all_names = template_crud.get_all_template_names(db)

    if not query:
        return all_names

    suggestions = [
        name for name in all_names
        if query.lower() in name.lower()
    ]
    return suggestions

@router.get("/", response_model=List[str])
def get_workout_template_exercises(
    template_name: str,
    db: Session = Depends(get_db)
):

    template = template_crud.get_template_by_name(db, template_name=template_name)
    if not template or not template.exercise_names:
        return []
    return template.exercise_names
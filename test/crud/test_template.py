import pytest
from unittest.mock import MagicMock
from app import models
from app.crud import template as crud_template

# --- Test: get_all_template_names ---

def test_get_all_template_names_empty(mock_db):
    """Test getting all template names when the database is empty."""
    # Setup: Query returns an empty list
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    
    result = crud_template.get_all_template_names(mock_db)
    
    assert result == []
    # Verify query structure: query(models.WorkoutTemplate.template_name)
    mock_db.query.assert_called_with(models.WorkoutTemplate.template_name)

def test_get_all_template_names_success(mock_db):
    """Test getting all template names returns a list of strings."""
    # Setup: DB returns a list of tuples (as SQLAlchemy does for single-column queries)
    mock_data = [("Chest Day",), ("Leg Day",), ("Back Day",)]
    mock_db.query.return_value.order_by.return_value.all.return_value = mock_data
    
    result = crud_template.get_all_template_names(mock_db)
    
    # Assert
    assert result == ["Chest Day", "Leg Day", "Back Day"]
    mock_db.query.return_value.order_by.assert_called_with(models.WorkoutTemplate.template_name)

# --- Test: get_template_by_name ---

def test_get_template_by_name_found(mock_db):
    """Test retrieving an existing template by name."""
    template_name = "Full Body"
    mock_template = models.WorkoutTemplate(id="t1", template_name=template_name, exercise_names=["Squat", "Bench"])
    
    mock_db.query.return_value.filter.return_value.first.return_value = mock_template
    
    result = crud_template.get_template_by_name(mock_db, template_name)
    
    assert result == mock_template
    assert result.template_name == template_name
    # Verify filter was called correctly (implicit check via execution flow, strict check difficult with expression objects)

def test_get_template_by_name_not_found(mock_db):
    """Test retrieving a non-existent template returns None."""
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    result = crud_template.get_template_by_name(mock_db, "NonExistent")
    
    assert result is None

# --- Test: create_template ---

def test_create_template_success(mock_db):
    """Test creating a new workout template."""
    template_name = "New Routine"
    exercises = ["Push Up", "Pull Up"]
    
    # Act
    result = crud_template.create_template(mock_db, template_name, exercises)
    
    # Assert
    assert isinstance(result, models.WorkoutTemplate)
    assert result.template_name == template_name
    assert result.exercise_names == exercises
    assert result.id is not None # UUID should be generated
    
    # Verify DB interactions
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(result)
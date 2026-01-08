import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app
from app import models
from app.security.security import get_api_key
from app.database import get_db

mock_db_session = MagicMock()

@pytest.fixture(autouse=True)
def setup_dependency_overrides():
    app.dependency_overrides[get_api_key] = lambda: "key"
    app.dependency_overrides[get_db] = lambda: mock_db_session
    yield
    app.dependency_overrides = {}
    mock_db_session.reset_mock()

client = TestClient(app)

def test_get_suggestions_all():
    mock_names = ["Chest A", "Chest B", "Legs"]
    with patch("app.routers.templates.template_crud.get_all_template_names", return_value=mock_names):
        response = client.get("/templates/suggestions")
        assert response.status_code == 200
        assert response.json() == mock_names

def test_get_suggestions_filtered():
    mock_names = ["Chest A", "Chest B", "Legs"]
    with patch("app.routers.templates.template_crud.get_all_template_names", return_value=mock_names):
        response = client.get("/templates/suggestions?query=chest")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert "Legs" not in data

def test_get_template_exercises_success():
    mock_template = models.WorkoutTemplate(template_name="Chest A", exercise_names=["Bench", "Fly"])
    with patch("app.routers.templates.template_crud.get_template_by_name", return_value=mock_template):
        response = client.get("/templates/?template_name=Chest A")
        assert response.status_code == 200
        assert response.json() == ["Bench", "Fly"]

def test_get_template_exercises_not_found():
    with patch("app.routers.templates.template_crud.get_template_by_name", return_value=None):
        response = client.get("/templates/?template_name=Unknown")
        assert response.status_code == 200
        assert response.json() == []
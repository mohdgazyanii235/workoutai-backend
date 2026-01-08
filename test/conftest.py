import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

@pytest.fixture
def mock_db():
    """
    Creates a mock database session. 
    This allows us to test CRUD functions without a running database.
    """
    session = MagicMock(spec=Session)
    return session
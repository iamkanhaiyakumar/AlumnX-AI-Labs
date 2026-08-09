import pytest
import os
import sys
from sqlalchemy import text

# Ensure the backend directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.seed import seed_users

@pytest.fixture(scope="session", autouse=True)
def setup_test_session():
    # Seed the team roster users in the database
    seed_users()
    yield

@pytest.fixture(scope="function")
def db():
    """
    Function-level fixture that yields a DB session and
    cleans up the tables after each test using TRUNCATE CASCADE.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        # Clean up database tables for the next test
        session.execute(text("TRUNCATE TABLE task_updates, processing_records, tasks, emails, runs CASCADE;"))
        session.commit()
        session.close()

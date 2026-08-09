from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import User
from ..schemas import UserResponse

router = APIRouter()

@router.get("/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    """
    Returns the official team roster.
    """
    users = db.query(User).all()
    return users

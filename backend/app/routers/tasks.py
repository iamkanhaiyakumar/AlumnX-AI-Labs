import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from ..models import Task, User
from ..schemas import TaskCreate, TaskUpdateSchema, TaskResponse

router = APIRouter()

@router.post("/tasks", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)):
    """
    Creates a new task. Enforces database-level uniqueness on (candidate_id, source_email_id).
    """
    # Normalize candidate_id
    candidate_id = task_in.candidate_id.strip().lower().replace(",", ".")

    # Verify assignee exists
    user = db.query(User).filter(User.user_id == task_in.assignee_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Assignee {task_in.assignee_id} does not exist"
        )

    # Generate task_id
    task_id = f"tsk_{uuid.uuid4().hex[:6]}"
    
    db_task = Task(
        task_id=task_id,
        candidate_id=candidate_id,
        source_email_id=task_in.source_email_id,
        thread_id=task_in.thread_id,
        title=task_in.title,
        description=task_in.description,
        assignee_id=task_in.assignee_id,
        category=task_in.category,
        priority=task_in.priority,
        due_date=task_in.due_date,
        deal_value_inr=task_in.deal_value_inr,
        company_name=task_in.company_name,
        confidence=task_in.confidence,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(db_task)
    try:
        db.commit()
        db.refresh(db_task)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task with candidate_id and source_email_id already exists"
        )

    return {
        "task_id": db_task.task_id,
        "candidate_id": db_task.candidate_id,
        "source_email_id": db_task.source_email_id,
        "created_at": db_task.created_at.isoformat() + "+05:30"  # Format similarly to brief example
    }

@router.get("/tasks", response_model=List[TaskResponse])
def get_tasks(
    candidate_id: str = Query(..., description="Normalised candidate email"),
    thread_id: Optional[str] = Query(None),
    source_email_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns tasks for the candidate, applying filters if provided.
    """
    candidate_id = candidate_id.strip().lower().replace(",", ".")
    query = db.query(Task).filter(Task.candidate_id == candidate_id)

    if thread_id:
        query = query.filter(Task.thread_id == thread_id)
    if source_email_id:
        query = query.filter(Task.source_email_id == source_email_id)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)

    return query.all()

@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: str, task_in: TaskUpdateSchema, db: Session = Depends(get_db)):
    """
    Updates specific task fields. Returns the full updated task.
    """
    db_task = db.query(Task).filter(Task.task_id == task_id).first()
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found"
        )

    update_data = task_in.model_dump(exclude_unset=True)

    # Validate assignee if changing
    if "assignee_id" in update_data:
        user = db.query(User).filter(User.user_id == update_data["assignee_id"]).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Assignee {update_data['assignee_id']} does not exist"
            )

    for field, value in update_data.items():
        setattr(db_task, field, value)

    db_task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_task)
    return db_task

@router.delete("/tasks/{task_id}", status_code=status.HTTP_200_OK)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    """
    Deletes a single task by ID.
    """
    db_task = db.query(Task).filter(Task.task_id == task_id).first()
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found"
        )
    db.delete(db_task)
    db.commit()
    return {"status": "success", "message": f"Task {task_id} deleted"}

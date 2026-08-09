from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ProcessingRecord, Email, Task

router = APIRouter()

@router.get("/api/tasks")
def get_api_tasks(
    candidate_id: str = Query(..., description="Normalised candidate email"),
    db: Session = Depends(get_db)
):
    """
    Returns a unified view of all processed emails (including skips) and their linked tasks.
    """
    candidate_id = candidate_id.strip().lower().replace(",", ".")
    results = []

    # Query processing records joined with Email details
    records = db.query(ProcessingRecord, Email).\
        join(Email, (ProcessingRecord.candidate_id == Email.candidate_id) & (ProcessingRecord.email_id == Email.email_id)).\
        filter(ProcessingRecord.candidate_id == candidate_id).\
        order_by(Email.received_at.desc()).all()

    for record, email in records:
        task_data = None
        if record.task_id:
            task = db.query(Task).filter(Task.task_id == record.task_id).first()
            if task:
                task_data = {
                    "task_id": task.task_id,
                    "title": task.title,
                    "description": task.description,
                    "assignee_id": task.assignee_id,
                    "category": task.category,
                    "priority": task.priority,
                    "due_date": task.due_date,
                    "deal_value_inr": task.deal_value_inr,
                    "company_name": task.company_name,
                    "confidence": task.confidence,
                    "updated_at": task.updated_at.isoformat()
                }

        results.append({
            "id": record.id,
            "email_id": record.email_id,
            "thread_id": record.thread_id,
            "run_id": record.run_id,
            "decision": record.decision,
            "category": record.category,
            "assignee_id": record.assignee_id,
            "confidence": record.confidence,
            "reason": record.reason,
            "skip_reason": record.skip_reason,
            "is_spurious": record.is_spurious,
            "email": {
                "from_name": email.from_name,
                "from_email": email.from_email,
                "subject": email.subject,
                "received_at": email.received_at.isoformat() if email.received_at else None,
                "body_preview": email.cleaned_body[:200]
            },
            "task": task_data
        })

    return results

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import IngestRequest, IngestResponse
from ..services.ingestion import process_batch

router = APIRouter()

@router.post("/ingest", response_model=IngestResponse)
def ingest_emails(payload: IngestRequest, db: Session = Depends(get_db)):
    """
    Synchronously ingests a batch of emails, classifies them,
    and updates/routes them to task owners.
    """
    if len(payload.emails) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size exceeds limit of 100 emails"
        )
        
    try:
        result = process_batch(
            candidate_id=payload.candidate_id,
            emails_in=payload.emails,
            db=db
        )
        
        return IngestResponse(
            processed=result["processed"],
            tasks_created=result["tasks_created"],
            tasks_updated=result["tasks_updated"],
            skipped=result["skipped"],
            errors=result["errors"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"In-process ingestion failure: {str(e)}"
        )

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Run, ProcessingRecord

router = APIRouter()

@router.get("/api/stats")
def get_stats(
    candidate_id: str = Query(..., description="Normalised candidate email"),
    db: Session = Depends(get_db)
):
    """
    Returns aggregate stats and run-level breakdowns.
    """
    candidate_id = candidate_id.strip().lower().replace(",", ".")

    # Retrieve all runs for the candidate to calculate totals
    runs = db.query(Run).filter(Run.candidate_id == candidate_id).all()

    total_processed = 0
    total_created = 0
    total_updated = 0
    total_skipped = 0
    total_duplicates = 0

    run_breakdowns = []
    for r in runs:
        total_processed += r.processed
        total_created += r.created
        total_updated += r.updated
        total_skipped += r.skipped
        total_duplicates += r.duplicates

        run_breakdowns.append({
            "run_id": r.run_id,
            "processed": r.processed,
            "created": r.created,
            "updated": r.updated,
            "skipped": r.skipped,
            "duplicates": r.duplicates,
            "start_time": r.start_time.isoformat() if r.start_time else None,
            "completion_time": r.completion_time.isoformat() if r.completion_time else None
        })

    # Retrieve total spurious records (OOO, newsletters, spam)
    spurious_count = db.query(func.count(ProcessingRecord.id)).\
        filter(ProcessingRecord.candidate_id == candidate_id).\
        filter(ProcessingRecord.is_spurious == True).scalar() or 0

    # Spurious rate = spurious tasks / total processed
    spurious_rate = 0.0
    if total_processed > 0:
        spurious_rate = spurious_count / total_processed

    # Retrieve category counts from processing_records
    category_counts = {}
    cat_query = db.query(ProcessingRecord.category, func.count(ProcessingRecord.id)).\
        filter(ProcessingRecord.candidate_id == candidate_id).\
        filter(ProcessingRecord.category.is_not(None)).\
        group_by(ProcessingRecord.category).all()
    
    for cat, count in cat_query:
        category_counts[cat] = count

    return {
        "processed": total_processed,
        "created": total_created,
        "updated": total_updated,
        "skipped": total_skipped,
        "duplicates": total_duplicates,
        "spurious_count": spurious_count,
        "spurious_rate": spurious_rate,
        "category_breakdown": category_counts,
        "runs": run_breakdowns
    }

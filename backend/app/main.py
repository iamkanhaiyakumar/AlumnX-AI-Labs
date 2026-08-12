from fastapi import FastAPI, Depends, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import get_db, engine
from .config import settings
from .routers import tasks, users, ingest, api_tasks, api_stats, api_chat

app = FastAPI(
    title="AlumnX AI Labs — Sales Inbox Task Router API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for frontend access
# Allows the configured FRONTEND_URL or local development default
allowed_origins = [
    settings.FRONTEND_URL,
    "http://localhost:5173",
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom validation error handler to override FastAPI's default 422
# for invalid assignee_id, category, or priority enum inputs to return custom 400
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    for error in exc.errors():
        loc = error.get("loc", [])
        msg = error.get("msg", "")
        type_ = error.get("type", "")
        
        # Check if the error is related to Enum values validation
        if "enum" in type_ or "enum" in msg or "value is not a valid enumeration member" in msg:
            field = loc[-1] if loc else "unknown"
            if field in ["assignee_id", "category", "priority"]:
                received = error.get("input", "unknown")
                
                # Match exact brief requirement enum lists
                allowed_map = {
                    "assignee_id": ["u_aarti", "u_rohit", "u_meera", "u_karan", "u_divya", "u_triage"],
                    "category": ["enterprise_rfp", "smb_enquiry", "marketing", "alliances", "finance", "triage"],
                    "priority": ["high", "medium", "low"]
                }
                
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error": "invalid_enum_value",
                        "field": field,
                        "received": str(received),
                        "allowed": allowed_map.get(field, [])
                    }
                )
                
    # Default handler fallback for other standard request validations (e.g. schema types mismatch)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )

# Health endpoint checking database connectivity
@app.get("/health", status_code=status.HTTP_200_OK)
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint verifying active database connection pool.
    """
    try:
        db.execute(text("SELECT 1;"))
        return {
            "status": "healthy",
            "database": "connected",
            "candidate_id": settings.CANDIDATE_ID
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": f"failed: {str(e)}",
                "candidate_id": settings.CANDIDATE_ID
            }
        )

# Register Admin API for resetting database
@app.post("/api/admin/clear-db", tags=["Admin API"])
def clear_database(db: Session = Depends(get_db)):
    """
    Deletes all Tasks, Emails, ProcessingRecords, Runs, and TaskUpdates associated with this candidate ID.
    Allows candidates to reset their database to a clean state for testing/demoing.
    """
    from .models import Task, Email, ProcessingRecord, Run, TaskUpdate
    try:
        candidate_id = settings.CANDIDATE_ID
        
        # Delete dependencies first
        db.query(TaskUpdate).filter(
            TaskUpdate.task_id.in_(
                db.query(Task.task_id).filter(Task.candidate_id == candidate_id)
            )
        ).delete(synchronize_session=False)
        
        db.query(Task).filter(Task.candidate_id == candidate_id).delete(synchronize_session=False)
        db.query(ProcessingRecord).filter(ProcessingRecord.candidate_id == candidate_id).delete(synchronize_session=False)
        db.query(Email).filter(Email.candidate_id == candidate_id).delete(synchronize_session=False)
        db.query(Run).filter(Run.candidate_id == candidate_id).delete(synchronize_session=False)
        
        db.commit()
        return {
            "message": "Database reset successful. All candidate tables have been cleared.",
            "candidate_id": candidate_id
        }
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "database_clear_failed",
                "detail": str(e)
            }
        )

# Register routes under single base URL
app.include_router(tasks.router, tags=["Task API"])
app.include_router(users.router, tags=["Users API"])
app.include_router(ingest.router, tags=["Ingestion API"])
app.include_router(api_tasks.router, tags=["Wrapper Tasks API"])
app.include_router(api_stats.router, tags=["Wrapper Stats API"])
app.include_router(api_chat.router, tags=["Conversational Chat API"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

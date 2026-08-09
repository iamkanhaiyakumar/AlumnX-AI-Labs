from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import ChatRequest, ChatResponse
from ..services.chat_engine import answer_chat_query

router = APIRouter()

@router.post("/api/chat", response_model=ChatResponse)
def chat_query(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    Exposes a grounded natural-language query interface over processed database data.
    """
    try:
        result = answer_chat_query(
            candidate_id=payload.candidate_id,
            query=payload.query,
            db=db
        )
        return ChatResponse(
            answer=result["answer"],
            supporting_data=result["supporting_data"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat query engine failed: {str(e)}"
        )

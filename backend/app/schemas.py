from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum

class AssigneeEnum(str, Enum):
    u_aarti = "u_aarti"
    u_rohit = "u_rohit"
    u_meera = "u_meera"
    u_karan = "u_karan"
    u_divya = "u_divya"
    u_triage = "u_triage"

class CategoryEnum(str, Enum):
    enterprise_rfp = "enterprise_rfp"
    smb_enquiry = "smb_enquiry"
    marketing = "marketing"
    alliances = "alliances"
    finance = "finance"
    triage = "triage"

class PriorityEnum(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

# User schema
class UserBase(BaseModel):
    user_id: str
    name: str
    department: str
    scope: str

class UserResponse(UserBase):
    class Config:
        from_attributes = True

# Task schema for /tasks API
class TaskCreate(BaseModel):
    candidate_id: str
    source_email_id: str
    thread_id: str
    title: str
    description: Optional[str] = None
    assignee_id: AssigneeEnum
    category: CategoryEnum
    priority: PriorityEnum
    due_date: Optional[str] = None  # YYYY-MM-DD or None
    deal_value_inr: Optional[int] = None  # Rupees integer or None
    company_name: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)

class TaskUpdateSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[AssigneeEnum] = None
    category: Optional[CategoryEnum] = None
    priority: Optional[PriorityEnum] = None
    due_date: Optional[str] = None
    deal_value_inr: Optional[int] = None
    company_name: Optional[str] = None
    confidence: Optional[float] = None

class TaskResponse(BaseModel):
    task_id: str
    candidate_id: str
    source_email_id: str
    thread_id: str
    title: str
    description: Optional[str] = None
    assignee_id: str
    category: str
    priority: str
    due_date: Optional[str] = None
    deal_value_inr: Optional[int] = None
    company_name: Optional[str] = None
    confidence: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Ingestion email schemas
class EmailInRequest(BaseModel):
    email_id: str
    thread_id: str
    message_index: int
    from_name: Optional[str] = None
    from_email: str
    to: str
    cc: Optional[List[str]] = None
    subject: str
    body: str
    received_at: str  # ISO-8601 string (e.g. 2026-08-01T09:14:22+05:30)
    attachments: Optional[List[str]] = None
    is_reply: bool = False

class IngestRequest(BaseModel):
    candidate_id: str
    emails: List[EmailInRequest]

class IngestResponse(BaseModel):
    processed: int
    tasks_created: int
    tasks_updated: int
    skipped: int
    duplicates: int = 0
    errors: List[str] = []

# Grounded Chat schemas
class ChatRequest(BaseModel):
    candidate_id: str
    query: str

class ChatResponse(BaseModel):
    answer: str
    supporting_data: Dict[str, Any]

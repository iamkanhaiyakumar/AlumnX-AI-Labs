from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, index=True)  # u_aarti, u_rohit, etc.
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    scope = Column(String, nullable=False)

    tasks = relationship("Task", back_populates="assignee")

class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String, nullable=False, index=True)
    email_id = Column(String, nullable=False, index=True)
    thread_id = Column(String, nullable=False, index=True)
    message_index = Column(Integer, nullable=False)
    from_name = Column(String, nullable=True)
    from_email = Column(String, nullable=False)
    to = Column(String, nullable=False)
    cc = Column(JSONB, nullable=True)  # List of emails
    subject = Column(String, nullable=False)
    body = Column(String, nullable=False)
    received_at = Column(DateTime, nullable=False)
    attachments = Column(JSONB, nullable=True)  # List of attachment filenames
    is_reply = Column(Boolean, nullable=False, default=False)
    raw_body = Column(String, nullable=False)
    cleaned_body = Column(String, nullable=False)
    
    # State tracking & lease logic
    processing_status = Column(String, nullable=False, default="processing", index=True)  # processing | completed | failed
    processing_started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processing_attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(String, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("candidate_id", "email_id", name="uq_candidate_email"),
        Index("idx_emails_candidate_status", "candidate_id", "processing_status"),
    )

class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True, index=True)  # tsk_...
    candidate_id = Column(String, nullable=False, index=True)
    source_email_id = Column(String, nullable=False, index=True)
    thread_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    assignee_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    category = Column(String, nullable=False, index=True)  # enterprise_rfp, etc.
    priority = Column(String, nullable=False, index=True)  # high, medium, low
    due_date = Column(String, nullable=True)  # YYYY-MM-DD
    deal_value_inr = Column(Integer, nullable=True)
    company_name = Column(String, nullable=True)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assignee = relationship("User", back_populates="tasks")
    updates = relationship("TaskUpdate", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("candidate_id", "source_email_id", name="uq_candidate_source_email"),
    )

class TaskUpdate(Base):
    __tablename__ = "task_updates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False, index=True)
    source_email_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=False, index=True)
    changed_fields = Column(JSONB, nullable=False)  # List of string fields changed
    previous_values = Column(JSONB, nullable=False)  # Dict of previous state
    new_values = Column(JSONB, nullable=False)  # Dict of new state
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    task = relationship("Task", back_populates="updates")

class ProcessingRecord(Base):
    __tablename__ = "processing_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String, nullable=False, index=True)
    email_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=False)
    run_id = Column(String, ForeignKey("runs.run_id"), nullable=False, index=True)
    decision = Column(String, nullable=False)  # created | updated | skipped | noop | error
    category = Column(String, nullable=True)
    assignee_id = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    reason = Column(String, nullable=True)
    skip_reason = Column(String, nullable=True)
    task_id = Column(String, ForeignKey("tasks.task_id", ondelete="SET NULL"), nullable=True)
    is_spurious = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class Run(Base):
    __tablename__ = "runs"

    run_id = Column(String, primary_key=True, index=True)  # run_...
    candidate_id = Column(String, nullable=False, index=True)
    processed = Column(Integer, nullable=False, default=0)
    created = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    skipped = Column(Integer, nullable=False, default=0)
    duplicates = Column(Integer, nullable=False, default=0)
    errors = Column(JSONB, nullable=True)  # List/dict of errors captured
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    completion_time = Column(DateTime, nullable=True)

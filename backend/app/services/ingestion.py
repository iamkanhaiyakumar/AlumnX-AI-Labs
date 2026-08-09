import uuid
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import json

from ..models import Email, Task, TaskUpdate, ProcessingRecord, Run, User
from ..schemas import EmailInRequest, IngestResponse
from .normalization import strip_html, clean_whitespace, extract_new_message
from .spam import detect_spam_deterministic
from .priority import calculate_priority
from .classifier import classify_new_email
from .thread import extract_task_updates

logger = logging.getLogger(__name__)

# Constants
LEASE_SECONDS = 900  # 15 minutes lease duration

def process_batch(candidate_id: str, emails_in: list[EmailInRequest], db: Session) -> dict:
    """
    Synchronously processes a batch of emails.
    Enforces atomic database-level idempotency, short transactions,
    thread updates vs. new task creations, and records run statistics.
    """
    candidate_id = candidate_id.strip().lower().replace(",", ".")
    run_id = f"run_{uuid.uuid4().hex[:6]}"
    
    # Initialize Run record
    db_run = Run(
        run_id=run_id,
        candidate_id=candidate_id,
        processed=0,
        created=0,
        updated=0,
        skipped=0,
        duplicates=0,
        errors=[],
        start_time=datetime.utcnow()
    )
    db.add(db_run)
    db.commit()

    run_errors = []

    for email_in in emails_in:
        # Normalize email fields
        normalized_email_id = email_in.email_id.strip()
        normalized_thread_id = email_in.thread_id.strip()
        received_at_dt = datetime.fromisoformat(email_in.received_at.replace("Z", "+00:00"))

        # TRANSACTION 1: Check and Claim Email
        # We check the database status of this email
        db_email = db.query(Email).filter(
            Email.candidate_id == candidate_id,
            Email.email_id == normalized_email_id
        ).first()

        claimed = False
        is_duplicate = False

        if db_email:
            if db_email.processing_status == "completed":
                is_duplicate = True
            elif db_email.processing_status == "processing":
                # Check if the processing lease has expired (stale)
                stale_time = datetime.utcnow() - timedelta(seconds=LEASE_SECONDS)
                if db_email.processing_started_at < stale_time:
                    # Atomic reclaim of stale email using CAS
                    updated_rows = db.query(Email).filter(
                        Email.candidate_id == candidate_id,
                        Email.email_id == normalized_email_id,
                        Email.processing_status == "processing",
                        Email.processing_started_at < stale_time
                    ).update({
                        "processing_status": "processing",
                        "processing_started_at": datetime.utcnow(),
                        "processing_attempts": Email.processing_attempts + 1
                    }, synchronize_session=False)
                    db.commit()
                    if updated_rows > 0:
                        claimed = True
                        db_email = db.query(Email).filter(
                            Email.candidate_id == candidate_id,
                            Email.email_id == normalized_email_id
                        ).first()
                else:
                    # Freshly processing in another request, bypass
                    continue
            elif db_email.processing_status == "failed":
                # Atomic claim of failed email using CAS for retry
                updated_rows = db.query(Email).filter(
                    Email.candidate_id == candidate_id,
                    Email.email_id == normalized_email_id,
                    Email.processing_status == "failed"
                ).update({
                    "processing_status": "processing",
                    "processing_started_at": datetime.utcnow(),
                    "processing_attempts": Email.processing_attempts + 1
                }, synchronize_session=False)
                db.commit()
                if updated_rows > 0:
                    claimed = True
                    db_email = db.query(Email).filter(
                        Email.candidate_id == candidate_id,
                        Email.email_id == normalized_email_id
                    ).first()
        else:
            # Brand new email, attempt insert
            cleaned_b = extract_new_message(email_in.body)
            db_email = Email(
                candidate_id=candidate_id,
                email_id=normalized_email_id,
                thread_id=normalized_thread_id,
                message_index=email_in.message_index,
                from_name=email_in.from_name,
                from_email=email_in.from_email,
                to=email_in.to,
                cc=email_in.cc,
                subject=email_in.subject,
                body=email_in.body,
                received_at=received_at_dt,
                attachments=email_in.attachments,
                is_reply=email_in.is_reply,
                raw_body=email_in.body,
                cleaned_body=cleaned_b,
                processing_status="processing",
                processing_started_at=datetime.utcnow(),
                processing_attempts=1,
                created_at=datetime.utcnow()
            )
            db.add(db_email)
            try:
                db.commit()
                claimed = True
            except IntegrityError:
                db.rollback()
                is_duplicate = True

        if is_duplicate:
            # Increment duplicate stats in Run and bypass processing
            db.query(Run).filter(Run.run_id == run_id).update({
                Run.duplicates: Run.duplicates + 1,
                Run.processed: Run.processed + 1
            })
            db.commit()
            continue

        if not claimed:
            continue

        # EMAIL IS CLAIMED. Perform out-of-transaction business operations (Gemini calls)
        try:
            # 1. Normalization & quoted extraction
            new_reply_text = extract_new_message(db_email.body)
            
            # 2. Check for existing thread AND active task
            existing_task = db.query(Task).filter(
                Task.candidate_id == candidate_id,
                Task.thread_id == normalized_thread_id
            ).first()

            if existing_task:
                # UPDATE WORKFLOW (Thread Reconciliation)
                # Gemini partial updates call (analyzing reply-only content)
                update_result = extract_task_updates(
                    reply_content=new_reply_text,
                    task_title=existing_task.title,
                    task_desc=existing_task.description or "",
                    task_assignee=existing_task.assignee_id,
                    task_category=existing_task.category,
                    task_priority=existing_task.priority,
                    task_due_date=existing_task.due_date,
                    task_deal_value=existing_task.deal_value_inr,
                    task_company=existing_task.company_name,
                    received_at_iso=db_email.received_at.isoformat()
                )

                changes = update_result.get("changes", {})
                confidence = update_result.get("confidence", 0.0)
                reason = update_result.get("reason", "")

                # TRANSACTION 2: Apply updates
                if changes:
                    # Create TaskUpdate record
                    previous_values = {k: getattr(existing_task, k) for k in changes.keys()}
                    
                    # Store update in Task
                    for k, v in changes.items():
                        setattr(existing_task, k, v)
                    existing_task.updated_at = datetime.utcnow()
                    
                    db_update = TaskUpdate(
                        task_id=existing_task.task_id,
                        source_email_id=normalized_email_id,
                        thread_id=normalized_thread_id,
                        changed_fields=list(changes.keys()),
                        previous_values=previous_values,
                        new_values=changes,
                        created_at=datetime.utcnow()
                    )
                    db.add(db_update)
                    
                    db_record = ProcessingRecord(
                        candidate_id=candidate_id,
                        email_id=normalized_email_id,
                        thread_id=normalized_thread_id,
                        run_id=run_id,
                        decision="updated",
                        category=existing_task.category,
                        assignee_id=existing_task.assignee_id,
                        confidence=confidence,
                        reason=reason,
                        task_id=existing_task.task_id,
                        is_spurious=False,
                        created_at=datetime.utcnow()
                    )
                    db.add(db_record)

                    db.query(Run).filter(Run.run_id == run_id).update({
                        Run.updated: Run.updated + 1,
                        Run.processed: Run.processed + 1
                    })
                else:
                    # No-op reply (decision="noop")
                    db_record = ProcessingRecord(
                        candidate_id=candidate_id,
                        email_id=normalized_email_id,
                        thread_id=normalized_thread_id,
                        run_id=run_id,
                        decision="noop",
                        reason=reason or "Reply contained no actionable task-field changes",
                        task_id=existing_task.task_id,
                        is_spurious=False,
                        created_at=datetime.utcnow()
                    )
                    db.add(db_record)
                    
                    db.query(Run).filter(Run.run_id == run_id).update({
                        Run.processed: Run.processed + 1
                    })

                # Mark email completed
                db_email.processing_status = "completed"
                db_email.processed_at = datetime.utcnow()
                db.commit()

            else:
                # NEW TASK WORKFLOW (Even if thread exists, but no active task exists)
                # 1. Deterministic skip checks
                skip_check = detect_spam_deterministic(db_email.subject, db_email.body)
                decision = None
                category = None
                assignee_id = None
                confidence = 1.0
                reason = ""
                skip_reason = ""
                is_spurious = False

                if skip_check.get("is_spam"):
                    decision = "skipped"
                    is_spurious = skip_check.get("is_spurious", False)
                    skip_reason = skip_check.get("reason", "")
                    reason = skip_reason
                else:
                    # Call Gemini for semantic intent and classification
                    llm_res = classify_new_email(db_email.subject, db_email.cleaned_body, db_email.received_at.isoformat())
                    decision = llm_res.decision
                    category = llm_res.category
                    assignee_id = llm_res.assignee_id
                    confidence = llm_res.confidence
                    reason = llm_res.reason
                    
                    # Direction of intent: Skip if Gemini classified it as skip (vendor spam/newsletter)
                    if decision == "skip":
                        decision = "skipped"
                        skip_reason = llm_res.reason
                        # Check if skipped because of unsolicited vendor spam or newsletters
                        is_spurious = any(x in llm_res.reason.lower() for x in ["spam", "vendor", "sell", "newsletter", "auto"])

                # TRANSACTION 2: Create task or skip record
                if decision == "skipped":
                    db_record = ProcessingRecord(
                        candidate_id=candidate_id,
                        email_id=normalized_email_id,
                        thread_id=normalized_thread_id,
                        run_id=run_id,
                        decision="skipped",
                        category=category,
                        assignee_id=assignee_id,
                        confidence=confidence,
                        reason=reason,
                        skip_reason=skip_reason,
                        task_id=None,
                        is_spurious=is_spurious,
                        created_at=datetime.utcnow()
                    )
                    db.add(db_record)

                    db.query(Run).filter(Run.run_id == run_id).update({
                        Run.skipped: Run.skipped + 1,
                        Run.processed: Run.processed + 1
                    })
                    db_email.processing_status = "completed"
                    db_email.processed_at = datetime.utcnow()
                    db.commit()

                else:
                    # ACTIONABLE: Apply deterministic overrides
                    # 1. PSU / Government tender override
                    is_psu = any(x in db_email.subject.lower() or x in db_email.body.lower() 
                                 for x in ["tender", "psu", "bhel", "procurement", "ntpc", "government"])
                    
                    if is_psu and (category == "enterprise_rfp" or category == "smb_enquiry" or "tender" in db_email.subject.lower()):
                        # Force Aarti & enterprise_rfp
                        category = "enterprise_rfp"
                        assignee_id = "u_aarti"
                        reason = f"[PSU Override] PSU/Government tender mapped to Aarti. Original: {reason}"

                    # 2. Extract and format due date
                    due_date = llm_res.due_date
                    
                    # 3. Extract deal value
                    deal_value_inr = llm_res.deal_value_inr
                    company_name = llm_res.company_name

                    # 4. Priority rule override: Deadline within 72 hours
                    priority = calculate_priority(db_email.received_at, due_date, llm_res.priority)

                    # Create Task
                    task_id = f"tsk_{uuid.uuid4().hex[:6]}"
                    db_task = Task(
                        task_id=task_id,
                        candidate_id=candidate_id,
                        source_email_id=normalized_email_id,
                        thread_id=normalized_thread_id,
                        title=email_in.subject,
                        description=f"From: {email_in.from_name} ({email_in.from_email})\n\n{new_reply_text}",
                        assignee_id=assignee_id,
                        category=category,
                        priority=priority,
                        due_date=due_date,
                        deal_value_inr=deal_value_inr,
                        company_name=company_name,
                        confidence=confidence,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(db_task)
                    db.flush()  # Flush task insert to resolve FK constraint on processing_records
                    
                    db_record = ProcessingRecord(
                        candidate_id=candidate_id,
                        email_id=normalized_email_id,
                        thread_id=normalized_thread_id,
                        run_id=run_id,
                        decision="created",
                        category=category,
                        assignee_id=assignee_id,
                        confidence=confidence,
                        reason=reason,
                        task_id=task_id,
                        is_spurious=False,
                        created_at=datetime.utcnow()
                    )
                    db.add(db_record)

                    db.query(Run).filter(Run.run_id == run_id).update({
                        Run.created: Run.created + 1,
                        Run.processed: Run.processed + 1
                    })
                    db_email.processing_status = "completed"
                    db_email.processed_at = datetime.utcnow()
                    db.commit()

        except Exception as e:
            # FAILURE TRANSACTION: Set status failed, log error
            logger.error(f"Failed to process email {normalized_email_id}: {e}", exc_info=True)
            db.rollback()
            
            # Short transaction to update Email to failed and store the error
            try:
                db_email.processing_status = "failed"
                db_email.last_error = str(e)
                
                # Append error details to Run.errors list
                error_msg = f"Email {normalized_email_id}: {str(e)}"
                run_errors.append(error_msg)
                
                db.query(Run).filter(Run.run_id == run_id).update({
                    Run.processed: Run.processed + 1,
                    Run.errors: Run.errors + [error_msg] if Run.errors else [error_msg]
                })
                db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to record processing failure state in database: {inner_e}")
                db.rollback()

    # Complete the Run
    completed_run = db.query(Run).filter(Run.run_id == run_id).first()
    completed_run.completion_time = datetime.utcnow()
    db.commit()

    return {
        "run_id": run_id,
        "processed": completed_run.processed,
        "tasks_created": completed_run.created,
        "tasks_updated": completed_run.updated,
        "skipped": completed_run.skipped,
        "duplicates": completed_run.duplicates,
        "errors": completed_run.errors or []
    }

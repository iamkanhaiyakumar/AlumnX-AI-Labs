import pytest
from unittest.mock import patch, MagicMock
from app.services.ingestion import process_batch
from app.services.classifier import GeminiNewTaskResponse
from app.models import Task, TaskUpdate, ProcessingRecord, Email

@patch("app.services.ingestion.classify_new_email")
@patch("app.services.ingestion.extract_task_updates")
def test_noop_thread_reply(mock_update, mock_classify, db):
    # Setup initial email creation
    mock_classify.return_value = GeminiNewTaskResponse(
        decision="create", category="smb_enquiry", assignee_id="u_rohit",
        priority="low", due_date=None, deal_value_inr=None,
        company_name="Acme Corp", confidence=0.9, reason="Initial"
    )

    email_1 = MagicMock(
        email_id="em_noop_001", thread_id="th_noop_001", message_index=0,
        from_name="Bob", from_email="bob@acme.com", to="sales@company.com",
        cc=[], subject="Question about product", body="Hi, can you send info?",
        received_at="2026-08-01T10:00:00+05:30", attachments=[], is_reply=False
    )
    process_batch("kanhaiyak0104@gmail.com", [email_1], db)
    
    task = db.query(Task).filter(Task.source_email_id == "em_noop_001").first()
    initial_updated_at = task.updated_at

    # Setup no-op reply response (changes is empty)
    mock_update.return_value = {
        "changes": {},
        "confidence": 0.95,
        "reason": "Just a acknowledgment reply without changes"
    }

    email_2 = MagicMock(
        email_id="em_noop_002", thread_id="th_noop_001", message_index=1,
        from_name="Bob", from_email="bob@acme.com", to="sales@company.com",
        cc=[], subject="Re: Question about product", body="Thanks for sending, we received it.",
        received_at="2026-08-02T10:00:00+05:30", attachments=[], is_reply=True
    )
    
    res = process_batch("kanhaiyak0104@gmail.com", [email_2], db)
    assert res["tasks_updated"] == 0
    assert res["processed"] == 1

    # Verify task was NOT updated
    db.refresh(task)
    assert task.updated_at == initial_updated_at

    # Verify NO TaskUpdate history row was written
    update_count = db.query(TaskUpdate).filter(TaskUpdate.task_id == task.task_id).count()
    assert update_count == 0

    # Verify ProcessingRecord decision is "noop"
    record = db.query(ProcessingRecord).filter(ProcessingRecord.email_id == "em_noop_002").first()
    assert record.decision == "noop"


@patch("app.services.ingestion.classify_new_email")
def test_existing_thread_without_task(mock_classify, db):
    # 1. First email: OOO -> skipped, no task created
    email_1 = MagicMock(
        email_id="em_reconcile_001", thread_id="th_reconcile_001", message_index=0,
        from_name="Alice", from_email="alice@northbridge.in", to="sales@company.com",
        cc=[], subject="Auto: Out of Office", body="I am out of office until 14th August.",
        received_at="2026-08-01T08:00:00+05:30", attachments=[], is_reply=False
    )
    res_1 = process_batch("kanhaiyak0104@gmail.com", [email_1], db)
    assert res_1["skipped"] == 1
    assert res_1["tasks_created"] == 0

    # Verify no task exists
    task_count = db.query(Task).filter(Task.thread_id == "th_reconcile_001").count()
    assert task_count == 0

    # 2. Second email: later actionable request in same thread -> fresh classification -> task created
    mock_classify.return_value = GeminiNewTaskResponse(
        decision="create", category="smb_enquiry", assignee_id="u_rohit",
        priority="low", due_date=None, deal_value_inr=None,
        company_name="Northbridge", confidence=0.92, reason="Fresh inquiry after return"
    )

    email_2 = MagicMock(
        email_id="em_reconcile_002", thread_id="th_reconcile_001", message_index=1,
        from_name="Alice", from_email="alice@northbridge.in", to="sales@company.com",
        cc=[], subject="Re: Out of Office", body="I am back. Can we get a demo scheduled?",
        received_at="2026-08-15T10:00:00+05:30", attachments=[], is_reply=True
    )
    
    res_2 = process_batch("kanhaiyak0104@gmail.com", [email_2], db)
    assert res_2["tasks_created"] == 1
    assert res_2["tasks_updated"] == 0

    # Verify task was successfully created
    task = db.query(Task).filter(Task.source_email_id == "em_reconcile_002").first()
    assert task is not None
    assert task.assignee_id == "u_rohit"

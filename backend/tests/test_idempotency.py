import pytest
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
from app.services.ingestion import process_batch
from app.services.classifier import GeminiNewTaskResponse
from app.models import Email, Task, ProcessingRecord, Run

@patch("app.services.ingestion.classify_new_email")
def test_duplicate_skipped_email(mock_classify, db):
    # Setup newsletter response (should trigger skipped is_spurious=True)
    mock_classify.return_value = GeminiNewTaskResponse(
        decision="skip",
        category="triage",
        assignee_id="u_triage",
        priority="low",
        due_date=None,
        deal_value_inr=None,
        company_name=None,
        confidence=0.99,
        reason="Weekly newsletter"
    )

    email = MagicMock(
        email_id="em_skip_001", thread_id="th_skip_001", message_index=0,
        from_name="News", from_email="news@newsletter.com",
        to="sales@company.com", cc=[], subject="SaaS Weekly newsletter",
        body="Weekly SaaS newsletter content. [Unsubscribe]",
        received_at="2026-08-01T10:00:00+05:30", attachments=[], is_reply=False
    )

    # Ingest 1
    res_1 = process_batch("kanhaiyak0104@gmail.com", [email], db)
    assert res_1["processed"] == 1
    assert res_1["skipped"] == 1
    assert res_1["duplicates"] == 0

    # Verify a ProcessingRecord was written
    record_count = db.query(ProcessingRecord).filter(ProcessingRecord.email_id == "em_skip_001").count()
    assert record_count == 1

    # Ingest 2 (Duplicate request)
    mock_classify.reset_mock()
    res_2 = process_batch("kanhaiyak0104@gmail.com", [email], db)
    assert res_2["processed"] == 1
    assert res_2["skipped"] == 0
    assert res_2["duplicates"] == 1

    # Verify Gemini was NOT called again
    mock_classify.assert_not_called()

    # Verify NO duplicate ProcessingRecord was written
    assert db.query(ProcessingRecord).filter(ProcessingRecord.email_id == "em_skip_001").count() == 1


@patch("app.services.ingestion.classify_new_email")
def test_concurrent_duplicate_ingestion(mock_classify, db):
    mock_classify.return_value = GeminiNewTaskResponse(
        decision="create",
        category="smb_enquiry",
        assignee_id="u_rohit",
        priority="low",
        due_date=None,
        deal_value_inr=None,
        company_name="Logistics Corp",
        confidence=0.92,
        reason="Actionable demo request"
    )

    email = MagicMock(
        email_id="em_concurrent_001", thread_id="th_concurrent_001", message_index=0,
        from_name="Alice", from_email="alice@logistics.com",
        to="sales@company.com", cc=[], subject="Demo Request",
        body="Hi, I'd like a demo.",
        received_at="2026-08-01T10:00:00+05:30", attachments=[], is_reply=False
    )

    # Define a helper function to run inside threads
    def run_ingest():
        # Open a new database session per thread to simulate true database concurrency
        from app.database import SessionLocal
        thread_db = SessionLocal()
        try:
            return process_batch("kanhaiyak0104@gmail.com", [email], thread_db)
        finally:
            thread_db.close()

    # Execute 2 concurrent ingestion requests in a thread pool
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run_ingest) for _ in range(2)]
        results = [f.result() for f in futures]

    # Exactly one request must successfully process/create
    # The other request must trigger unique constraint violation and mark as duplicate
    total_created = sum(r["tasks_created"] for r in results)
    total_duplicates = sum(r["duplicates"] for r in results)
    
    assert total_created == 1
    assert total_duplicates == 1

    # Verify database state has exactly 1 email, 1 task, and 1 processing record
    assert db.query(Email).filter(Email.email_id == "em_concurrent_001").count() == 1
    assert db.query(Task).filter(Task.source_email_id == "em_concurrent_001").count() == 1
    assert db.query(ProcessingRecord).filter(ProcessingRecord.email_id == "em_concurrent_001").count() == 1

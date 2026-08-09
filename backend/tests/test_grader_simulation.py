import pytest
from unittest.mock import patch, MagicMock
from app.services.ingestion import process_batch
from app.services.classifier import GeminiNewTaskResponse
from app.models import Task, Email, ProcessingRecord, Run, TaskUpdate

# Setup responses for tests
MOCK_NEW_TASK = GeminiNewTaskResponse(
    decision="create",
    category="enterprise_rfp",
    assignee_id="u_aarti",
    priority="medium",
    due_date="2026-08-15",
    deal_value_inr=3000000,
    company_name="Nexus Corp",
    confidence=0.95,
    reason="RFP above 10L"
)

@patch("app.services.ingestion.classify_new_email")
@patch("app.services.ingestion.extract_task_updates")
def test_grader_simulation(mock_update, mock_classify, db):
    mock_classify.return_value = MOCK_NEW_TASK
    mock_update.return_value = {
        "changes": {"deal_value_inr": 3500000, "priority": "high"},
        "confidence": 0.96,
        "reason": "Budget increased to 35L"
    }

    # RUN 1: Ingest Fresh Email
    email_batch = [
        MagicMock(
            email_id="em_sim_001", thread_id="th_sim_001", message_index=0,
            from_name="John Doe", from_email="john@nexuscorp.com",
            to="sales@company.com", cc=[], subject="RFP Nexus Corp",
            body="Nexus Corp invites proposals. Budget: Rs. 30 lakhs. Due: 15-08-2026.",
            received_at="2026-08-01T10:00:00+05:30", attachments=[], is_reply=False
        )
    ]

    res_1 = process_batch("kanhaiyak0104@gmail.com", email_batch, db)
    assert res_1["processed"] == 1
    assert res_1["tasks_created"] == 1
    assert res_1["tasks_updated"] == 0
    assert res_1["skipped"] == 0
    assert res_1["duplicates"] == 0

    # Verify task was created
    task = db.query(Task).filter(Task.source_email_id == "em_sim_001").first()
    assert task is not None
    assert task.assignee_id == "u_aarti"
    assert task.deal_value_inr == 3000000

    # RUN 2: Re-ingest the Same Email (Idempotency check)
    mock_classify.reset_mock() # Reset mock to verify it is NOT called during duplicate ingestion
    
    res_2 = process_batch("kanhaiyak0104@gmail.com", email_batch, db)
    assert res_2["processed"] == 1
    assert res_2["tasks_created"] == 0
    assert res_2["tasks_updated"] == 0
    assert res_2["skipped"] == 0
    assert res_2["duplicates"] == 1

    # Verify Gemini was never called
    mock_classify.assert_not_called()

    # Verify task count remains exactly 1
    task_count = db.query(Task).filter(Task.candidate_id == "kanhaiyak0104@gmail.com").count()
    assert task_count == 1

    # Verify no duplicate Email row was created
    email_rows = db.query(Email).filter(Email.email_id == "em_sim_001").count()
    assert email_rows == 1

    # RUN 3: Ingest thread reply (Thread reconciliation check)
    reply_batch = [
        MagicMock(
            email_id="em_sim_002", thread_id="th_sim_001", message_index=1,
            from_name="John Doe", from_email="john@nexuscorp.com",
            to="sales@company.com", cc=[], subject="Re: RFP Nexus Corp",
            body="Budget increased to 35 lakhs.\n\nOn Sun, Aug 1, 2026...",
            received_at="2026-08-02T10:00:00+05:30", attachments=[], is_reply=True
        )
    ]

    res_3 = process_batch("kanhaiyak0104@gmail.com", reply_batch, db)
    assert res_3["processed"] == 1
    assert res_3["tasks_updated"] == 1
    assert res_3["tasks_created"] == 0
    assert res_3["duplicates"] == 0

    # Verify existing task updated
    db.refresh(task)
    assert task.deal_value_inr == 3500000
    assert task.priority == "high"

    # Verify TaskUpdate history record was written
    update_rec = db.query(TaskUpdate).filter(TaskUpdate.task_id == task.task_id).first()
    assert update_rec is not None
    assert update_rec.source_email_id == "em_sim_002"
    assert "deal_value_inr" in update_rec.changed_fields

    # Verify task count remains 1
    assert db.query(Task).filter(Task.candidate_id == "kanhaiyak0104@gmail.com").count() == 1

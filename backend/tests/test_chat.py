import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import func
from app.services.chat_engine import parse_user_query, execute_structured_query, answer_chat_query, StructuredChatQuery
from app.models import Task, Email, ProcessingRecord, Run, TaskUpdate

# Pre-define mock queries to test parsing
MOCK_QUERIES = {
    "How many high priority tasks?": StructuredChatQuery(
        intent="count", source="tasks", scope="all",
        filters={"priority": "high"}, reasoning="Count tasks with high priority."
    ),
    "How many emails were skipped in the current batch?": StructuredChatQuery(
        intent="count", source="processing_records", scope="current_batch",
        filters={"decision": "skipped"}, reasoning="Count skipped emails in latest batch."
    ),
    "What is our spurious rate so far?": StructuredChatQuery(
        intent="rate", source="processing_records", scope="all",
        filters={}, reasoning="Compute spurious rate across all history."
    ),
    "What is the total deal value of all open RFPs?": StructuredChatQuery(
        intent="aggregate", source="tasks", scope="all",
        filters={"category": "enterprise_rfp"}, aggregate_field="deal_value_inr",
        reasoning="Sum deal value for enterprise RFPs."
    )
}

def side_effect_parse(query):
    return MOCK_QUERIES.get(query, StructuredChatQuery(
        intent="list", source="tasks", scope="all", filters={}, reasoning="default"
    ))

@patch("app.services.chat_engine.parse_user_query", side_effect=side_effect_parse)
@patch("app.services.chat_engine.call_gemini_with_retry")
def test_grounded_chat(mock_call, mock_parse, db):
    # Set up some dummy data in DB
    run = Run(run_id="run_chat_01", candidate_id="kanhaiyak0104@gmail.com", processed=3, created=2, skipped=1, duplicates=0)
    db.add(run)
    db.commit()
    
    # 2 Tasks
    task_1 = Task(task_id="tsk_c1", candidate_id="kanhaiyak0104@gmail.com", source_email_id="em_c1", thread_id="th_c1", title="RFP 1", assignee_id="u_aarti", category="enterprise_rfp", priority="high", deal_value_inr=3000000, confidence=0.9)
    task_2 = Task(task_id="tsk_c2", candidate_id="kanhaiyak0104@gmail.com", source_email_id="em_c2", thread_id="th_c2", title="Demo 2", assignee_id="u_rohit", category="smb_enquiry", priority="low", deal_value_inr=None, confidence=0.8)
    db.add(task_1)
    db.add(task_2)
    
    # Processing records
    rec_1 = ProcessingRecord(candidate_id="kanhaiyak0104@gmail.com", email_id="em_c1", thread_id="th_c1", run_id="run_chat_01", decision="created", category="enterprise_rfp", is_spurious=False)
    rec_2 = ProcessingRecord(candidate_id="kanhaiyak0104@gmail.com", email_id="em_c2", thread_id="th_c2", run_id="run_chat_01", decision="created", category="smb_enquiry", is_spurious=False)
    rec_3 = ProcessingRecord(candidate_id="kanhaiyak0104@gmail.com", email_id="em_c3", thread_id="th_c3", run_id="run_chat_01", decision="skipped", category=None, is_spurious=True, skip_reason="OOO")
    db.add(rec_1)
    db.add(rec_2)
    db.add(rec_3)
    
    # Emails
    em_1 = Email(candidate_id="kanhaiyak0104@gmail.com", email_id="em_c1", thread_id="th_c1", message_index=0, from_email="a@a.com", to="b@b.com", subject="RFP", body="RFP", received_at=db.query(func.now()).scalar(), raw_body="RFP", cleaned_body="RFP")
    em_2 = Email(candidate_id="kanhaiyak0104@gmail.com", email_id="em_c2", thread_id="th_c2", message_index=0, from_email="a@a.com", to="b@b.com", subject="Demo", body="Demo", received_at=db.query(func.now()).scalar(), raw_body="Demo", cleaned_body="Demo")
    em_3 = Email(candidate_id="kanhaiyak0104@gmail.com", email_id="em_c3", thread_id="th_c3", message_index=0, from_email="a@a.com", to="b@b.com", subject="OOO", body="OOO", received_at=db.query(func.now()).scalar(), raw_body="OOO", cleaned_body="OOO")
    db.add(em_1)
    db.add(em_2)
    db.add(em_3)
    
    db.commit()

    # Test 1: Task count query
    res_1 = execute_structured_query("kanhaiyak0104@gmail.com", MOCK_QUERIES["How many high priority tasks?"], db)
    assert res_1["count"] == 1
    assert res_1["source"] == "tasks"

    # Test 2: Ingest stats query (skipped in current batch)
    # We update run completion time so it's resolved as the latest completed run
    run.completion_time = db.query(func.now()).scalar()
    db.commit()
    
    res_2 = execute_structured_query("kanhaiyak0104@gmail.com", MOCK_QUERIES["How many emails were skipped in the current batch?"], db)
    assert res_2["count"] == 1
    assert res_2["run_id"] == "run_chat_01"

    # Test 3: Spurious rate
    res_3 = execute_structured_query("kanhaiyak0104@gmail.com", MOCK_QUERIES["What is our spurious rate so far?"], db)
    # 1 spurious record out of 3 total processed
    assert res_3["spurious_count"] == 1
    assert res_3["processed"] == 3
    assert res_3["spurious_rate"] == 1.0 / 3.0

    # Test 4: Aggregate deal value
    res_4 = execute_structured_query("kanhaiyak0104@gmail.com", MOCK_QUERIES["What is the total deal value of all open RFPs?"], db)
    assert res_4["total_deal_value_inr"] == 3000000
    assert res_4["rfps_with_no_stated_value"] == 0

    # Test 5: Call answer_chat_query with LLM phrasing failure fallback
    # Mock Gemini answer generation to fail (throws exception)
    mock_call.side_effect = Exception("Rate limit or connection drop")
    
    chat_res = answer_chat_query("kanhaiyak0104@gmail.com", "How many high priority tasks?", db)
    assert "1" in chat_res["answer"]
    assert chat_res["supporting_data"]["count"] == 1

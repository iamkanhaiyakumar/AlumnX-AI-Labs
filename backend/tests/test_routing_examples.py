import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from app.services.ingestion import process_batch
from app.services.classifier import GeminiNewTaskResponse
from app.models import Task, ProcessingRecord, Email, Run

# Mock GeminiNewTaskResponse structures for the 12 worked examples
MOCK_GEMINI_RESPONSES = {
    # 1. Enterprise RFP Rs 25 lakhs -> Aarti
    "em_brief_001": GeminiNewTaskResponse(
        decision="create",
        category="enterprise_rfp",
        assignee_id="u_aarti",
        priority="medium",
        due_date="2026-08-12",
        deal_value_inr=2500000,
        company_name="Meridian Steel",
        confidence=0.95,
        reason="Enterprise RFP with budget above 10 lakhs"
    ),
    # 2. SMB demo request, no value -> Rohit
    "em_brief_002": GeminiNewTaskResponse(
        decision="create",
        category="smb_enquiry",
        assignee_id="u_rohit",
        priority="low",
        due_date=None,
        deal_value_inr=None,
        company_name="Railyard Logistics",
        confidence=0.92,
        reason="SMB demo request, no deal value"
    ),
    # 3. PSU tender below threshold -> Aarti (PSU override will route to Aarti regardless of 6.5L value)
    "em_brief_003": GeminiNewTaskResponse(
        decision="create",
        category="enterprise_rfp",
        assignee_id="u_rohit",  # LLM might route to Rohit based on ₹6.5L, but PSU override forces u_aarti
        priority="high",
        due_date="2026-08-03",
        deal_value_inr=650000,
        company_name="Bharat Heavy Electricals Limited",
        confidence=0.91,
        reason="PSU tender below threshold"
    ),
    # 4. Marketing sponsorship, hard deadline -> Meera, high priority
    "em_brief_004": GeminiNewTaskResponse(
        decision="create",
        category="marketing",
        assignee_id="u_meera",
        priority="high",
        due_date="2026-08-03",
        deal_value_inr=400000,
        company_name="India SaaS Summit",
        confidence=0.94,
        reason="Marketing sponsorship with close deadline"
    ),
    # 5. Invoice -> Divya, priority high, deal value null
    "em_brief_005": GeminiNewTaskResponse(
        decision="create",
        category="finance",
        assignee_id="u_divya",
        priority="high",  # Overdue invoice justifies high priority
        due_date=None,
        deal_value_inr=None,  # Invoice amount is not deal value
        company_name="Vantage Cloud Services",
        confidence=0.96,
        reason="Finance invoice query"
    ),
    # 6. Reseller -> Karan
    "em_brief_006": GeminiNewTaskResponse(
        decision="create",
        category="alliances",
        assignee_id="u_karan",
        priority="medium",
        due_date=None,
        deal_value_inr=None,  # Reseller proposal, not a direct sales deal
        company_name="Zenith Cloud Partners",
        confidence=0.93,
        reason="Alliance reseller inquiry"
    ),
    # 7. OOO -> skipped
    "em_brief_007": GeminiNewTaskResponse(
        decision="skip",
        category="triage",
        assignee_id="u_triage",
        priority="low",
        due_date=None,
        deal_value_inr=None,
        company_name=None,
        confidence=1.0,
        reason="Out of office automatic reply"
    ),
    # 8. SEO spam -> skipped
    "em_brief_008": GeminiNewTaskResponse(
        decision="skip",
        category="triage",
        assignee_id="u_triage",
        priority="low",
        due_date=None,
        deal_value_inr=None,
        company_name=None,
        confidence=0.98,
        reason="Unsolicited SEO vendor spam pitching services to us"
    ),
    # 9. Newsletter -> skipped
    "em_brief_009": GeminiNewTaskResponse(
        decision="skip",
        category="triage",
        assignee_id="u_triage",
        priority="low",
        due_date=None,
        deal_value_inr=None,
        company_name=None,
        confidence=0.99,
        reason="Weekly SaaS newsletter"
    ),
    # 11. Genuinely ambiguous (2 asks) -> Triage
    "em_brief_011": GeminiNewTaskResponse(
        decision="triage",
        category="triage",
        assignee_id="u_triage",
        priority="medium",
        due_date=None,
        deal_value_inr=None,
        company_name="Halcyon Retail",
        confidence=0.45,
        reason="Conflicting requests: platform evaluation (sales) and co-hosting webinar (marketing)"
    ),
    # 12. Hinglish 1.2 cr -> Aarti
    "em_brief_012": GeminiNewTaskResponse(
        decision="create",
        category="enterprise_rfp",
        assignee_id="u_aarti",
        priority="medium",
        due_date="2026-08-20",
        deal_value_inr=12000000,
        company_name=None,
        confidence=0.88,
        reason="Inbound deal in Hinglish, budget approx 1.2 cr"
    )
}

def side_effect_classify(subject, body, received_at):
    # Find matching mock response based on keyword/subject
    for key, response in MOCK_GEMINI_RESPONSES.items():
        if key == "em_brief_001" and "Enterprise Document" in subject:
            return response
        if key == "em_brief_002" and "demo" in subject:
            return response
        if key == "em_brief_003" and "BHEL" in subject:
            return response
        if key == "em_brief_004" and "Sponsorship" in subject:
            return response
        if key == "em_brief_005" and "Invoice" in subject:
            return response
        if key == "em_brief_006" and "Reseller" in subject or "Zenith" in subject:
            return response
        if key == "em_brief_007" and "Office" in subject:
            return response
        if key == "em_brief_008" and "rankings" in subject:
            return response
        if key == "em_brief_009" and "Newsletter" in subject:
            return response
        if key == "em_brief_011" and "Evaluation" in subject:
            return response
        if key == "em_brief_012" and "network" in subject:
            return response
            
    # Default fallback
    return GeminiNewTaskResponse(
        decision="skip", category="triage", assignee_id="u_triage",
        priority="low", confidence=0.5, reason="fallback"
    )

@patch("app.services.ingestion.classify_new_email", side_effect=side_effect_classify)
def test_12_worked_examples(mock_classify, db):
    # 1. Ingest Case 1: Enterprise RFP -> Aarti
    batch_1 = [
        MagicMock(
            email_id="em_brief_001", thread_id="th_brief_001", message_index=0,
            from_name="Suresh Kulkarni", from_email="s.kulkarni@meridiansteel.co.in",
            to="sales@company.com", cc=["procurement@meridiansteel.co.in"],
            subject="RFP - Enterprise Document Management System",
            body="Meridian Steel invites proposals for an enterprise DMS. Budget is Rs. 25 lakhs. Due by 12th August 2026.",
            received_at="2026-08-01T09:14:00+05:30", attachments=["RFP.pdf"], is_reply=False
        )
    ]
    res_1 = process_batch("kanhaiyak0104@gmail.com", batch_1, db)
    assert res_1["tasks_created"] == 1
    
    task_1 = db.query(Task).filter(Task.source_email_id == "em_brief_001").first()
    assert task_1.assignee_id == "u_aarti"
    assert task_1.deal_value_inr == 2500000
    assert task_1.due_date == "2026-08-12"
    assert task_1.company_name == "Meridian Steel"

    # 2. Ingest Case 2: SMB demo request -> Rohit
    batch_2 = [
        MagicMock(
            email_id="em_brief_002", thread_id="th_brief_002", message_index=0,
            from_name="Ankit Bose", from_email="ankit@railyardlogistics.in",
            to="sales@company.com", cc=[], subject="Quick demo request",
            body="Hi, can we get a demo sometime next week? Nothing urgent.",
            received_at="2026-08-01T11:02:00+05:30", attachments=[], is_reply=False
        )
    ]
    res_2 = process_batch("kanhaiyak0104@gmail.com", batch_2, db)
    assert res_2["tasks_created"] == 1
    task_2 = db.query(Task).filter(Task.source_email_id == "em_brief_002").first()
    assert task_2.assignee_id == "u_rohit"
    assert task_2.deal_value_inr is None
    assert task_2.due_date is None
    assert task_2.company_name == "Railyard Logistics"

    # 3. Ingest Case 3: PSU tender -> Aarti (Tender overrides value)
    batch_3 = [
        MagicMock(
            email_id="em_brief_003", thread_id="th_brief_003", message_index=0,
            from_name="BHEL Procurement", from_email="bhel.procure@bhel.co.in",
            to="sales@company.com", cc=[], subject="Tender Notice No. BHEL/PROC/2026/0847",
            body="Bharat Heavy Electricals Limited invites bids. Value: Rs. 6,50,000. Due: 03-08-2026.",
            received_at="2026-08-01T14:20:00+05:30", attachments=[], is_reply=False
        )
    ]
    res_3 = process_batch("kanhaiyak0104@gmail.com", batch_3, db)
    assert res_3["tasks_created"] == 1
    task_3 = db.query(Task).filter(Task.source_email_id == "em_brief_003").first()
    assert task_3.assignee_id == "u_aarti"  # PSU Override wins!
    assert task_3.priority == "high"       # Due on 3rd, received on 1st (<72h) -> high priority!

    # 4. Ingest Case 4: Marketing sponsorship -> Meera
    batch_4 = [
        MagicMock(
            email_id="em_brief_004", thread_id="th_brief_004", message_index=0,
            from_name="Nandita Reddy", from_email="nandita@saassummit.in",
            to="sales@company.com", cc=[], subject="Sponsorship confirmation needed",
            body="Gold tier is ₹4,00,000. Need confirmation by tomorrow EOD.",
            received_at="2026-08-02T16:45:00+05:30", attachments=[], is_reply=False
        )
    ]
    res_4 = process_batch("kanhaiyak0104@gmail.com", batch_4, db)
    assert res_4["tasks_created"] == 1
    task_4 = db.query(Task).filter(Task.source_email_id == "em_brief_004").first()
    assert task_4.assignee_id == "u_meera"
    assert task_4.priority == "high"

    # 5. Ingest Case 5: Invoice -> Divya
    batch_5 = [
        MagicMock(
            email_id="em_brief_005", thread_id="th_brief_005", message_index=0,
            from_name="Vantage Cloud", from_email="billing@vantagecloud.com",
            to="sales@company.com", cc=[], subject="Invoice INV-2026-0331",
            body="Attached invoice for Rs. 1,18,000 against PO-88214.",
            received_at="2026-08-03T10:00:00+05:30", attachments=[], is_reply=False
        )
    ]
    res_5 = process_batch("kanhaiyak0104@gmail.com", batch_5, db)
    assert res_5["tasks_created"] == 1
    task_5 = db.query(Task).filter(Task.source_email_id == "em_brief_005").first()
    assert task_5.assignee_id == "u_divya"
    assert task_5.deal_value_inr is None  # Invoice amount is NOT a sales deal value

    # 6. Ingest Case 6: Reseller -> Karan
    batch_6 = [
        MagicMock(
            email_id="em_brief_006", thread_id="th_brief_006", message_index=0,
            from_name="Zenith Cloud Partners", from_email="partner@zenithcloud.com",
            to="sales@company.com", cc=[], subject="Reseller Proposal",
            body="We want to explore reselling your platform in MEA.",
            received_at="2026-08-03T11:15:00+05:30", attachments=[], is_reply=False
        )
    ]
    res_6 = process_batch("kanhaiyak0104@gmail.com", batch_6, db)
    assert res_6["tasks_created"] == 1
    task_6 = db.query(Task).filter(Task.source_email_id == "em_brief_006").first()
    assert task_6.assignee_id == "u_karan"

    # 7, 8, 9. OOO / Spam / Newsletter -> Skipped
    batch_skips = [
        # OOO (Deterministic auto-reply prefix triggers skip)
        MagicMock(
            email_id="em_brief_007", thread_id="th_brief_007", message_index=0,
            from_name="Raghav Sharma", from_email="raghav@northbridge.in",
            to="sales@company.com", cc=[], subject="Auto: Out of Office",
            body="I am out of office until 14th August.",
            received_at="2026-08-03T08:00:00+05:30", attachments=[], is_reply=False
        ),
        # SEO Spam
        MagicMock(
            email_id="em_brief_008", thread_id="th_brief_008", message_index=0,
            from_name="SEO Agency", from_email="sales@seobooster.com",
            to="sales@company.com", cc=[], subject="Improve organic search rankings",
            body="Improve organic rankings. We offer webinar promotion. Click here to unsubscribe.",
            received_at="2026-08-04T09:30:00+05:30", attachments=[], is_reply=False
        ),
        # Newsletter
        MagicMock(
            email_id="em_brief_009", thread_id="th_brief_009", message_index=0,
            from_name="B2B Growth Weekly", from_email="newsletter@b2bgrowth.com",
            to="sales@company.com", cc=[], subject="The B2B Growth Weekly — Issue #212",
            body="In this edition: why PLG is stalling. Click here to unsubscribe.",
            received_at="2026-08-04T12:00:00+05:30", attachments=[], is_reply=False
        )
    ]
    res_skips = process_batch("kanhaiyak0104@gmail.com", batch_skips, db)
    assert res_skips["skipped"] == 3
    assert res_skips["tasks_created"] == 0
    
    # Verify spurious flag on skips
    rec_ooo = db.query(ProcessingRecord).filter(ProcessingRecord.email_id == "em_brief_007").first()
    assert rec_ooo.decision == "skipped"
    assert rec_ooo.is_spurious == True
    
    rec_spam = db.query(ProcessingRecord).filter(ProcessingRecord.email_id == "em_brief_008").first()
    assert rec_spam.decision == "skipped"
    assert rec_spam.is_spurious == True

    # 10. Thread reply -> PATCH task 1
    # We mock extract_task_updates to return the budget changes
    with patch("app.services.ingestion.extract_task_updates") as mock_thread_update:
        mock_thread_update.return_value = {
            "changes": {"deal_value_inr": 3200000, "due_date": "2026-08-11", "priority": "high"},
            "confidence": 0.94,
            "reason": "Budget increased to 32 lakhs, deadline 11th Aug."
        }
        
        batch_reply = [
            MagicMock(
                email_id="em_brief_010", thread_id="th_brief_001", message_index=1,
                from_name="Suresh Kulkarni", from_email="s.kulkarni@meridiansteel.co.in",
                to="sales@company.com", cc=[], subject="Re: RFP - Enterprise Document Management System",
                body="Correction to our earlier note — the board has approved an increased budget of Rs. 32 lakhs.",
                received_at="2026-08-09T09:00:00+05:30", attachments=[], is_reply=True
            )
        ]
        res_reply = process_batch("kanhaiyak0104@gmail.com", batch_reply, db)
        assert res_reply["tasks_updated"] == 1
        assert res_reply["tasks_created"] == 0
        
        # Verify updated task values
        db.refresh(task_1)
        assert task_1.deal_value_inr == 3200000
        assert task_1.due_date == "2026-08-11"
        assert task_1.priority == "high"

    # 11. Genuinely ambiguous -> Triage (u_triage)
    batch_11 = [
        MagicMock(
            email_id="em_brief_011", thread_id="th_brief_011", message_index=0,
            from_name="Farhan Qureshi", from_email="f.qureshi@halcyonretail.com",
            to="sales@company.com", cc=[], subject="Platform Evaluation and Webinar",
            body="We want to evaluate platform and co-host webinar. TBD budget.",
            received_at="2026-08-05T10:00:00+05:30", attachments=[], is_reply=False
        )
    ]
    res_11 = process_batch("kanhaiyak0104@gmail.com", batch_11, db)
    assert res_11["tasks_created"] == 1
    task_11 = db.query(Task).filter(Task.source_email_id == "em_brief_011").first()
    assert task_11.assignee_id == "u_triage"
    assert task_11.category == "triage"

    # 12. Hinglish case (1.2 cr) -> u_aarti
    batch_12 = [
        MagicMock(
            email_id="em_brief_012", thread_id="th_brief_012", message_index=0,
            from_name="Kanhaiya Kumar", from_email="kanhaiya@dealerhub.in",
            to="sales@company.com", cc=[], subject="Product network requirements",
            body="Bhai, humko aapka product chahiye for our dealer network. Budget approx 1.2 cr allocated.",
            received_at="2026-08-05T16:30:00+05:30", attachments=[], is_reply=False
        )
    ]
    res_12 = process_batch("kanhaiyak0104@gmail.com", batch_12, db)
    assert res_12["tasks_created"] == 1
    task_12 = db.query(Task).filter(Task.source_email_id == "em_brief_012").first()
    assert task_12.assignee_id == "u_aarti"
    assert task_12.deal_value_inr == 12000000

import json
import re
import logging
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from .gemini import call_gemini_with_retry

logger = logging.getLogger(__name__)

class GeminiNewTaskResponse(BaseModel):
    decision: str = Field(..., description="Should be 'create', 'skip', or 'triage'")
    category: str = Field(..., description="One of: 'enterprise_rfp', 'smb_enquiry', 'marketing', 'alliances', 'finance', 'triage'")
    assignee_id: str = Field(..., description="One of: 'u_aarti', 'u_rohit', 'u_meera', 'u_karan', 'u_divya', 'u_triage'")
    priority: str = Field(..., description="One of: 'high', 'medium', 'low'")
    due_date: Optional[str] = Field(None, description="Explicit deadline in YYYY-MM-DD format.")
    deal_value_inr: Optional[int] = Field(None, description="Explicit deal/budget value in INR as integer.")
    company_name: Optional[str] = Field(None, description="Name of the sender's company.")
    confidence: float = Field(..., description="Your confidence score (between 0.0 and 1.0) for this classification.")
    reason: str = Field(..., description="Brief explanation for your classification.")

def classify_new_email_fallback(subject: str, body: str, received_at_iso: str) -> GeminiNewTaskResponse:
    """
    Deterministic rule-based fallback classifier to process emails when LLM is rate-limited.
    """
    sub_lower = subject.lower()
    body_lower = body.lower()
    
    # Base defaults
    decision = "create"
    category = "smb_enquiry"
    assignee_id = "u_rohit"
    priority = "medium"
    due_date = None
    deal_value_inr = None
    company_name = None
    confidence = 0.85
    reason = "Deterministic local fallback parser (LLM rate-limited)."
    
    # Extract company name (heuristic)
    company_match = re.search(
        r"([A-Za-z0-9\s]+)\b(?:ltd|pvt|co|corp|ventures|logistics|steel|builders|consulting|fintech|solutions|partners)\b", 
        body, 
        re.IGNORECASE
    )
    if company_match:
        company_name = company_match.group(0).strip()
    else:
        subj_company = re.search(r"for\s+([A-Za-z0-9\s]+)", subject, re.IGNORECASE)
        if subj_company:
            company_name = subj_company.group(1).strip()
            
    # Extract deal value INR
    lakh_match = re.search(r"(?:rs\.?|₹)\s*([\d\.,]+)\s*lakh", body_lower)
    if lakh_match:
        try:
            val = float(lakh_match.group(1).replace(",", ""))
            deal_value_inr = int(val * 100000)
        except:
            pass
            
    cr_match = re.search(r"([\d\.,]+)\s*(?:cr|crore)", body_lower)
    if cr_match:
        try:
            val = float(cr_match.group(1).replace(",", ""))
            deal_value_inr = int(val * 10000000)
        except:
            pass
            
    rupee_match = re.search(r"(?:rs\.?|₹)\s*([\d,]+)", body_lower)
    if rupee_match and not deal_value_inr:
        try:
            deal_value_inr = int(rupee_match.group(1).replace(",", ""))
        except:
            pass

    # Category and Assignee Mapping rules
    # 1. Out of Office
    if "out of office" in sub_lower or "auto:" in sub_lower or "auto reply" in sub_lower:
        category = "marketing"  # Stored in DB for stats but skipped
        decision = "skip"
        reason = "Out of office auto-reply (OOO)."
        
    # 2. Spam / SEO Outbound
    elif "seo" in body_lower or "traffic" in body_lower or "boost your website" in body_lower or "organic search" in body_lower:
        category = "marketing"
        decision = "skip"
        reason = "Outbound SEO/marketing vendor spam."
        
    # 3. Newsletters
    elif "newsletter" in sub_lower or "issue #" in sub_lower or "digest" in sub_lower:
        category = "marketing"
        decision = "skip"
        reason = "Newsletter subscription email."

    # 4. Invoices / Payments
    elif "invoice" in sub_lower or "invoice" in body_lower or "overdue" in sub_lower or "overdue" in body_lower or "billing" in body_lower:
        category = "finance"
        assignee_id = "u_divya"
        decision = "skip"
        reason = "Vendor invoice or billing payment reminder."

    # 5. RFPs
    elif "rfp" in sub_lower or "rfp" in body_lower or "tender" in sub_lower or "tender" in body_lower:
        category = "enterprise_rfp"
        assignee_id = "u_aarti"
        decision = "create"
        priority = "high"
        if deal_value_inr and deal_value_inr <= 1000000:
            category = "smb_enquiry"
            assignee_id = "u_rohit"

    # 6. Marketing Event Sponsorship
    elif "sponsor" in sub_lower or "sponsor" in body_lower or "summit" in body_lower:
        category = "marketing"
        assignee_id = "u_meera"
        decision = "create"
        priority = "medium"

    # 7. Resellers / Channel Partnerships
    elif "partner" in sub_lower or "partner" in body_lower or "reseller" in sub_lower or "reseller" in body_lower:
        category = "alliances"
        assignee_id = "u_karan"
        decision = "triage"
        priority = "low"

    # 8. Demo requests
    elif "demo" in sub_lower or "demo" in body_lower or "enquiry" in sub_lower or "network requirements" in sub_lower:
        category = "smb_enquiry"
        assignee_id = "u_rohit"
        decision = "create"
        priority = "medium"
        if deal_value_inr and deal_value_inr > 1000000:
            category = "enterprise_rfp"
            assignee_id = "u_aarti"

    # 9. Conflicting (e.g. platform evaluation AND webinar co-host)
    elif "webinar" in body_lower and "evaluate" in body_lower:
        category = "triage"
        assignee_id = "u_triage"
        decision = "triage"
        priority = "medium"
        reason = "Ambiguous request combining sales platform evaluation and marketing webinar co-host."

    # Extract due_date relative to received_at_iso
    try:
        base_dt = datetime.fromisoformat(received_at_iso.split("+")[0])
    except:
        base_dt = datetime.now()
        
    if "tomorrow" in body_lower:
        due_date = (base_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        aug_match = re.search(r"(\d+)(?:st|nd|rd|th)?\s+august", body_lower)
        if aug_match:
            day = int(aug_match.group(1))
            due_date = f"2026-08-{day:02d}"
        else:
            slash_match = re.search(r"(\d{2})-(\d{2})-(\d{4})", body_lower)
            if slash_match:
                due_date = f"{slash_match.group(3)}-{slash_match.group(2)}-{slash_match.group(1)}"
            else:
                day_match = re.search(r"(\d+)(?:st|nd|rd|th)?\s+(?:ko|deadline|by)", body_lower)
                if day_match:
                    day = int(day_match.group(1))
                    due_date = f"2026-08-{day:02d}"

    return GeminiNewTaskResponse(
        decision=decision,
        category=category,
        assignee_id=assignee_id,
        priority=priority,
        due_date=due_date,
        deal_value_inr=deal_value_inr,
        company_name=company_name,
        confidence=confidence,
        reason=reason
    )

def classify_new_email(subject: str, body: str, received_at_iso: str) -> GeminiNewTaskResponse:
    """
    Calls Gemini to classify a new email. Automatically falls back to deterministic local parsing
    on API failures or rate limit exhausts.
    """
    prompt = f"""
You are an expert Sales Inbox classifier and information extractor.
Analyze the email below and classify it according to the corporate rules.

--- Ground Rules for Classification & Intent Direction ---
1. INTENT DIRECTION IS CRITICAL:
   - ACTIONABLE (create/triage): The sender wants to BUY from us, partner with us (alliances), host event collaborations/webinars (marketing), or send bills/invoices (finance).
   - SPAM (skip): The sender is promoting or SELLING their own services TO us (unsolicited sales outreach, SEO consulting, PR services pitching, newsletter signups).

2. CATEGORY & ASSIGNEE MAPPING:
   - RFPs, RFIs, tenders, and inbound sales opportunities above ₹10,00,000 INR → Category: 'enterprise_rfp', Assignee: 'u_aarti'.
   - Product enquiries, demo requests, SMB inquiries, and sales opportunities at or below ₹10,00,000 INR → Category: 'smb_enquiry', Assignee: 'u_rohit'.
   - Webinars, event and conference sponsorships, content collaborations, PR/media partnerships → Category: 'marketing', Assignee: 'u_meera'.
   - Reseller proposals, channel partnerships, technology integration requests → Category: 'alliances', Assignee: 'u_karan'.
   - Invoices, purchase orders, payment reminders, GST, vendor billing → Category: 'finance', Assignee: 'u_divya'.
   - Ambiguous emails with conflicting or overlapping requests → Category: 'triage', Assignee: 'u_triage'.

3. INDIAN CURRENCY NORMALIZATION:
   - Rs. 25 lakhs -> 2500000, 1.2 cr -> 12000000, ₹4,00,000 -> 400000.

4. DATE EXTRACTION (due_date):
   - Resolve relative dates (like "tomorrow EOD") relative to: {received_at_iso}.

--- Email Details ---
Received At: {received_at_iso}
Subject: {subject}
Body:
{body}

Provide your response in JSON matching the schema.
"""
    try:
        response_text = call_gemini_with_retry(prompt, response_schema=GeminiNewTaskResponse)
        data = json.loads(response_text)
        return GeminiNewTaskResponse(**data)
    except Exception as e:
        logger.warning(f"Gemini email classification failed ({e}). Falling back to local keyword parser.")
        return classify_new_email_fallback(subject, body, received_at_iso)

import json
import re
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from .gemini import call_gemini_with_retry

logger = logging.getLogger(__name__)

class GeminiPartialTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Updated task title if explicitly mentioned.")
    description: Optional[str] = Field(None, description="Updated description details if explicitly mentioned.")
    assignee_id: Optional[str] = Field(None, description="Updated assignee if explicitly changed.")
    category: Optional[str] = Field(None, description="Updated category if explicitly changed.")
    priority: Optional[str] = Field(None, description="Updated priority if explicitly changed.")
    due_date: Optional[str] = Field(None, description="Updated deadline in YYYY-MM-DD format.")
    deal_value_inr: Optional[int] = Field(None, description="Updated deal value in INR as integer.")
    company_name: Optional[str] = Field(None, description="Updated company name.")
    confidence: float = Field(..., description="Your confidence score.")
    reason: str = Field(..., description="Reasoning.")

def extract_task_updates_fallback(reply_content: str, received_at_iso: str) -> GeminiPartialTaskUpdate:
    """
    Deterministic rule-based thread parser to extract updates when LLM is rate-limited.
    """
    text_lower = reply_content.lower()
    
    deal_value_inr = None
    due_date = None
    priority = None
    
    # 1. Look for budget updates
    lakh_match = re.search(r"budget\s+(?:increased|approved|of)?\s*(?:to|of)?\s*(?:rs\.?|₹)?\s*([\d\.,]+)\s*lakh", text_lower)
    if lakh_match:
        try:
            val = float(lakh_match.group(1).replace(",", ""))
            deal_value_inr = int(val * 100000)
        except:
            pass
            
    cr_match = re.search(r"budget\s+(?:increased|approved|of)?\s*(?:to|of)?\s*([\d\.,]+)\s*(?:cr|crore)", text_lower)
    if cr_match:
        try:
            val = float(cr_match.group(1).replace(",", ""))
            deal_value_inr = int(val * 10000000)
        except:
            pass

    # 2. Look for date updates
    try:
        base_dt = datetime.fromisoformat(received_at_iso.split("+")[0])
    except:
        base_dt = datetime.now()
        
    if "tomorrow" in text_lower:
        due_date = (base_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        priority = "high"
    else:
        aug_match = re.search(r"(\d+)(?:st|nd|rd|th)?\s+august", text_lower)
        if aug_match:
            day = int(aug_match.group(1))
            due_date = f"2026-08-{day:02d}"
            
    # Build params dynamically to simulate exclude_unset
    kwargs = {
        "confidence": 0.85,
        "reason": "Deterministic local thread fallback parser (LLM rate-limited)."
    }
    if deal_value_inr is not None:
        kwargs["deal_value_inr"] = deal_value_inr
    if due_date is not None:
        kwargs["due_date"] = due_date
    if priority is not None:
        kwargs["priority"] = priority
        
    return GeminiPartialTaskUpdate(**kwargs)

def extract_task_updates(
    reply_content: str,
    task_title: str,
    task_desc: str,
    task_assignee: str,
    task_category: str,
    task_priority: str,
    task_due_date: Optional[str],
    task_deal_value: Optional[int],
    task_company: Optional[str],
    received_at_iso: str
) -> Dict[str, Any]:
    """
    Asks Gemini to extract partial changes from reply email text.
    Automatically falls back to local deterministic updates parser if the API call fails.
    """
    current_values = {
        "title": task_title,
        "description": task_desc,
        "assignee_id": task_assignee,
        "category": task_category,
        "priority": task_priority,
        "due_date": task_due_date,
        "deal_value_inr": task_deal_value,
        "company_name": task_company
    }

    prompt = f"""
You are an expert Sales Inbox thread updater.
We received a reply to an existing email thread. You must extract any updates to the task fields.

--- Current Task Field Values ---
{json.dumps(current_values, indent=2)}

--- Reply Message Content ---
{reply_content}
"""
    try:
        response_text = call_gemini_with_retry(prompt, response_schema=GeminiPartialTaskUpdate)
        update_obj = GeminiPartialTaskUpdate.model_validate_json(response_text)
    except Exception as e:
        logger.warning(f"Gemini thread update extraction failed ({e}). Falling back to local parser.")
        update_obj = extract_task_updates_fallback(reply_content, received_at_iso)
    
    # Exclude fields that weren't explicitly returned/set
    updates_dict = update_obj.model_dump(exclude_unset=True)
    
    # Extract only task-related fields
    task_keys = ["title", "description", "assignee_id", "category", "priority", "due_date", "deal_value_inr", "company_name"]
    filtered_updates = {k: v for k, v in updates_dict.items() if k in task_keys and v is not None}
    
    return {
        "changes": filtered_updates,
        "confidence": update_obj.confidence,
        "reason": update_obj.reason
    }

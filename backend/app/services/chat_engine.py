import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Task, Email, ProcessingRecord, Run, TaskUpdate
from .gemini import call_gemini_with_retry

logger = logging.getLogger(__name__)

class StructuredChatQuery(BaseModel):
    intent: str = Field(..., description="One of: 'count', 'list', 'aggregate', 'rate', 'comparison', 'thread_history', 'unsupported_action'")
    source: str = Field(..., description="One of: 'tasks', 'processing_records', 'runs', 'task_updates'")
    scope: str = Field(..., description="One of: 'current_batch', 'all'")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Key-value filters. Supported keys: 'category' (marketing, finance etc), 'priority' (high, medium, low), 'assignee_id' (u_aarti, u_rohit etc), 'is_spurious' (true/false), 'decision' (created, skipped etc), and 'q' (generic text search for names, subjects, companies, like 'kanhaiya' or 'meridian').")
    aggregate_field: Optional[str] = Field(None, description="Field to aggregate (e.g. 'deal_value_inr' for sum).")
    target_thread_id: Optional[str] = Field(None, description="Thread ID if querying a specific thread.")
    is_out_of_scope: bool = Field(False, description="True if user requests an action like sending an email or modifying systems.")
    reasoning: str = Field(..., description="Brief explanation for query construction.")

def parse_user_query_fallback(query: str) -> StructuredChatQuery:
    """
    Translates a user natural language query into a StructuredChatQuery using rule-based keyword matching when Gemini fails.
    """
    q_lower = query.lower()
    
    intent = "list"
    source = "tasks"
    scope = "all"
    filters = {}
    aggregate_field = None
    target_thread_id = None
    is_out_of_scope = False
    
    # Scope detection
    if any(x in q_lower for x in ["this batch", "current batch", "latest run", "last run", "just pasted", "just generated"]):
        scope = "current_batch"
        
    # Out of scope detection
    if any(x in q_lower for x in ["send email", "send an email", "assign ", "delete ", "write to ", "contact "]):
        is_out_of_scope = True
        
    # Source detection
    if any(x in q_lower for x in ["processed", "skipped", "spurious", "auto-reply", "spam", "newsletter", "ooo", "out of office"]):
        source = "processing_records"
        if "spurious" in q_lower:
            filters["is_spurious"] = True
        if "skipped" in q_lower or "skips" in q_lower:
            filters["decision"] = "skipped"
        if "created" in q_lower:
            filters["decision"] = "created"
    elif any(x in q_lower for x in ["run stats", "run statistics", "batch stats", "batch statistics", "runs stats", "run details"]):
        source = "runs"
    else:
        source = "tasks"

    # Intent detection
    if any(x in q_lower for x in ["how many", "count", "number of", "total", "totals"]):
        intent = "count"
    elif any(x in q_lower for x in ["rate", "percentage", "ratio"]):
        intent = "rate"
        source = "processing_records"
    elif any(x in q_lower for x in ["aggregate", "sum", "value", "worth", "deal value", "budget"]):
        intent = "aggregate"
        aggregate_field = "deal_value_inr"
        
    # Thread history detection
    if "updated" in q_lower or "thread" in q_lower:
        if "more than once" in q_lower or "multiple times" in q_lower:
            intent = "thread_history"
            source = "task_updates"
            
    # Apply filters for specific fields if intent is list/count
    if intent in ["list", "count", "aggregate"]:
        # Priority filters
        if "high" in q_lower:
            filters["priority"] = "high"
        elif "medium" in q_lower:
            filters["priority"] = "medium"
        elif "low" in q_lower:
            filters["priority"] = "low"
            
        # Assignee
        if "aarti" in q_lower:
            filters["assignee_id"] = "u_aarti"
        elif "rohit" in q_lower:
            filters["assignee_id"] = "u_rohit"
        elif "meera" in q_lower:
            filters["assignee_id"] = "u_meera"
        elif "karan" in q_lower:
            filters["assignee_id"] = "u_karan"
        elif "divya" in q_lower:
            filters["assignee_id"] = "u_divya"
        elif "triage" in q_lower:
            filters["assignee_id"] = "u_triage"
            
        # Category filters
        if "marketing" in q_lower:
            filters["category"] = "marketing"
        elif "rfp" in q_lower or "proposal" in q_lower:
            filters["category"] = "enterprise_rfp"
        elif "alliance" in q_lower or "partner" in q_lower:
            filters["category"] = "alliances"
        elif "finance" in q_lower or "invoice" in q_lower:
            filters["category"] = "finance"

        # Add support for generic query search (unrecognized terms like 'kanhaiya')
        if source in ["tasks", "processing_records"]:
            search_term = None
            search_prefixes = ["containing ", "about ", "subject ", "with ", "search ", "from "]
            for prefix in search_prefixes:
                if prefix in q_lower:
                    idx = q_lower.index(prefix) + len(prefix)
                    search_term = query[idx:].strip()
                    if search_term.endswith("?"):
                        search_term = search_term[:-1].strip()
                    if search_term.endswith("."):
                        search_term = search_term[:-1].strip()
                    break
            
            if not search_term:
                matched_any_filter = "priority" in filters or "assignee_id" in filters or "category" in filters or "decision" in filters or "is_spurious" in filters
                if not matched_any_filter:
                    stop_words = ["list", "show", "tasks", "emails", "get", "find", "all", "me", "what", "how", "many", "count", "about", "the", "from", "for", "of", "to", "by", "in", "with", "on", "at", "a", "an", "any", "some", "task", "active", "status", "queries", "query", "details", "detail", "total", "totals", "number", "numbers", "sum", "aggregate", "processed", "created", "updated", "skipped", "skips", "spurious", "rate", "runs", "run", "batch", "routed", "route", "routing"]
                    words = [w for w in query.split() if w.lower().strip("?.!,") not in stop_words]
                    if words:
                        search_term = " ".join(words)
                    
            if search_term:
                st_clean = search_term.lower().strip()
                if st_clean not in ["rfp proposals", "rfp proposal", "rfp", "proposals", "proposal", "marketing", "alliance", "alliances", "finance"]:
                    filters["q"] = search_term
            
    return StructuredChatQuery(
        intent=intent,
        source=source,
        scope=scope,
        filters=filters,
        aggregate_field=aggregate_field,
        target_thread_id=target_thread_id,
        is_out_of_scope=is_out_of_scope,
        reasoning="Local keyword parser fallback."
    )

def parse_user_query(query: str) -> StructuredChatQuery:
    """
    Uses Gemini to translate a user natural language query into a StructuredChatQuery object.
    """
    prompt = f"""
You are an expert SQL-translator assistant. Your job is to translate a user's natural language question about a B2B sales routing database into a structured query object.
We support four tables:
1. 'tasks' (tracks active routed tasks: category, priority, assignee_id, due_date, deal_value_inr, company_name)
2. 'processing_records' (tracks EVERY email processed: decision, category, assignee_id, confidence, is_spurious, skip_reason)
3. 'runs' (tracks ingest batch statistics: processed, created, updated, skipped, duplicates)
4. 'task_updates' (tracks task changes over threads: task_id, thread_id, changed_fields)

Ground Rules:
- TASK QUESTIONS: (e.g. "how many high priority tasks?", "list Meera's tasks") → source: 'tasks'
- PROCESSING STATS: (e.g. "how many emails skipped/processed?", "how many marketing emails received?") → source: 'processing_records' (skips and auto-replies don't create tasks, so stats must query processing_records).
- RUN DETAILS: (e.g. "what was the duplicates count in the last batch?") → source: 'runs'
- THREAD HISTORY: (e.g. "did any thread get updated more than once?") → source: 'task_updates'
- KEYWORD SEARCH: If the user is asking about a specific person's name (e.g., 'rambabu kkr', 'kanhaiya'), email address, company name, or subject keyword that does not match standard fields, extract it into the 'q' filter (e.g., {"q": "rambabu kkr"}). Do NOT put category keywords (like 'RFP', 'proposal', 'marketing', 'alliance', 'finance') in the 'q' search filter. Instead, map them to the 'category' filter (e.g. {"category": "enterprise_rfp"}).
- SCOPE:
  - If the question mentions "this batch", "current batch", "latest run", "last run" → scope: 'current_batch'
  - Otherwise, default to scope: 'all'
- OUT OF SCOPE ACTIONS: If the user asks to "send an email", "assign a task to someone", "reply to Suresh", set is_out_of_scope = true.

User Query: "{query}"

Provide your output in JSON matching the schema.
"""
    response_text = call_gemini_with_retry(prompt, response_schema=StructuredChatQuery)
    data = json.loads(response_text)
    return StructuredChatQuery(**data)

def get_latest_run_id(candidate_id: str, db: Session) -> Optional[str]:
    """
    Gets the latest completed run_id for the candidate.
    """
    run = db.query(Run).filter(
        Run.candidate_id == candidate_id,
        Run.completion_time.is_not(None)
    ).order_by(Run.start_time.desc()).first()
    return run.run_id if run else None

def execute_structured_query(candidate_id: str, s_query: StructuredChatQuery, db: Session) -> Dict[str, Any]:
    """
    Translates a StructuredChatQuery into SQLAlchemy queries over the PostgreSQL database.
    Returns supporting_data matching the query requirements.
    """
    latest_run_id = get_latest_run_id(candidate_id, db)
    
    result_data = {
        "source": s_query.source,
        "scope": s_query.scope,
        "run_id": latest_run_id,
    }

    if s_query.is_out_of_scope:
        result_data["error"] = "out_of_scope_action"
        result_data["message"] = "The system only answers questions about processed sales inbox data and cannot perform external actions."
        return result_data

    # 1. Querying TASKS
    if s_query.source == "tasks":
        # Scoping logic
        if s_query.scope == "current_batch":
            if not latest_run_id:
                result_data["tasks_count"] = 0
                result_data["tasks_list"] = []
                return result_data
            
            # Resolve tasks via Run -> ProcessingRecord -> Email -> Task relationship
            query = db.query(Task).\
                join(Email, (Task.candidate_id == Email.candidate_id) & (Task.source_email_id == Email.email_id)).\
                join(ProcessingRecord, (Email.candidate_id == ProcessingRecord.candidate_id) & (Email.email_id == ProcessingRecord.email_id)).\
                filter(ProcessingRecord.run_id == latest_run_id)
        else:
            query = db.query(Task).filter(Task.candidate_id == candidate_id)

        # Apply filters
        filters = s_query.filters
        if "category" in filters:
            query = query.filter(Task.category == filters["category"])
        if "priority" in filters:
            query = query.filter(Task.priority == filters["priority"])
        if "assignee_id" in filters:
            query = query.filter(Task.assignee_id == filters["assignee_id"])
        if "company_name" in filters:
            query = query.filter(Task.company_name.ilike(f"%{filters['company_name']}%"))
            
        # Join with Email to filter by sender details or generic term 'q'
        if "from_name" in filters or "from_email" in filters or "q" in filters:
            if s_query.scope != "current_batch":
                query = query.join(Email, (Task.candidate_id == Email.candidate_id) & (Task.source_email_id == Email.email_id))
            
            if "from_name" in filters:
                query = query.filter(Email.from_name.ilike(f"%{filters['from_name']}%"))
            if "from_email" in filters:
                query = query.filter(Email.from_email.ilike(f"%{filters['from_email']}%"))
            if "q" in filters:
                term = filters["q"]
                if term.lower().strip() not in ["rfp proposals", "rfp proposal", "rfp", "proposals", "proposal", "marketing", "alliance", "alliances", "finance"]:
                    term_pct = f"%{term}%"
                    query = query.filter(
                        Task.title.ilike(term_pct) |
                        Task.description.ilike(term_pct) |
                        Task.company_name.ilike(term_pct) |
                        Email.from_name.ilike(term_pct) |
                        Email.from_email.ilike(term_pct) |
                        Email.subject.ilike(term_pct)
                    )

        if s_query.intent == "count":
            count_val = query.count()
            result_data["count"] = count_val
        elif s_query.intent == "list":
            tasks = query.all()
            result_data["tasks"] = []
            for t in tasks:
                email_obj = db.query(Email).filter(Email.email_id == t.source_email_id).first()
                result_data["tasks"].append({
                    "task_id": t.task_id,
                    "title": t.title,
                    "assignee_id": t.assignee_id,
                    "category": t.category,
                    "priority": t.priority,
                    "due_date": t.due_date,
                    "deal_value_inr": t.deal_value_inr,
                    "company_name": t.company_name,
                    "confidence": t.confidence,
                    "from_name": email_obj.from_name if email_obj else None,
                    "from_email": email_obj.from_email if email_obj else None
                })
        elif s_query.intent == "aggregate" and s_query.aggregate_field == "deal_value_inr":
            # Sum deal value and also count how many tasks had null deal value
            tasks = query.all()
            total_value = sum(t.deal_value_inr for t in tasks if t.deal_value_inr is not None)
            tasks_with_no_value = sum(1 for t in tasks if t.deal_value_inr is None)
            result_data["total_deal_value_inr"] = total_value
            result_data["rfps_with_no_stated_value"] = tasks_with_no_value
            result_data["count"] = len(tasks)

    # 2. Querying PROCESSING RECORDS
    elif s_query.source == "processing_records":
        if s_query.scope == "current_batch":
            if not latest_run_id:
                result_data["count"] = 0
                return result_data
            query = db.query(ProcessingRecord).filter(
                ProcessingRecord.candidate_id == candidate_id,
                ProcessingRecord.run_id == latest_run_id
            )
        else:
            query = db.query(ProcessingRecord).filter(ProcessingRecord.candidate_id == candidate_id)

        # Apply filters
        filters = s_query.filters
        if "category" in filters:
            query = query.filter(ProcessingRecord.category == filters["category"])
        if "decision" in filters:
            query = query.filter(ProcessingRecord.decision == filters["decision"])
        if "is_spurious" in filters:
            query = query.filter(ProcessingRecord.is_spurious == filters["is_spurious"])
        if "assignee_id" in filters:
            query = query.filter(ProcessingRecord.assignee_id == filters["assignee_id"])
            
        # Join with Email to filter by sender details or generic term 'q'
        if "from_name" in filters or "from_email" in filters or "q" in filters:
            query = query.join(Email, (ProcessingRecord.candidate_id == Email.candidate_id) & (ProcessingRecord.email_id == Email.email_id))
                
            if "from_name" in filters:
                query = query.filter(Email.from_name.ilike(f"%{filters['from_name']}%"))
            if "from_email" in filters:
                query = query.filter(Email.from_email.ilike(f"%{filters['from_email']}%"))
            if "q" in filters:
                term = filters["q"]
                if term.lower().strip() not in ["rfp proposals", "rfp proposal", "rfp", "proposals", "proposal", "marketing", "alliance", "alliances", "finance"]:
                    term_pct = f"%{term}%"
                    query = query.filter(
                        Email.from_name.ilike(term_pct) |
                        Email.from_email.ilike(term_pct) |
                        Email.subject.ilike(term_pct) |
                        Email.body.ilike(term_pct)
                    )

        if s_query.intent == "count":
            result_data["count"] = query.count()
        elif s_query.intent == "list":
            records = query.all()
            result_data["records"] = [
                {
                    "email_id": r.email_id,
                    "decision": r.decision,
                    "category": r.category,
                    "assignee_id": r.assignee_id,
                    "reason": r.reason,
                    "skip_reason": r.skip_reason,
                    "is_spurious": r.is_spurious,
                    "task_id": r.task_id
                } for r in records
            ]
        elif s_query.intent == "rate":
            # Spurious rate = spurious_count / processed_count
            total_count = query.count()
            spurious_count = query.filter(ProcessingRecord.is_spurious == True).count()
            rate = spurious_count / total_count if total_count > 0 else 0.0
            result_data["spurious_count"] = spurious_count
            result_data["processed"] = total_count
            result_data["spurious_rate"] = rate

    # 3. Querying RUNS
    elif s_query.source == "runs":
        if s_query.scope == "current_batch":
            if not latest_run_id:
                result_data["run"] = None
                return result_data
            run = db.query(Run).filter(Run.run_id == latest_run_id).first()
        else:
            run = db.query(Run).filter(Run.candidate_id == candidate_id).order_by(Run.start_time.desc()).first()

        if run:
            result_data["run"] = {
                "run_id": run.run_id,
                "processed": run.processed,
                "created": run.created,
                "updated": run.updated,
                "skipped": run.skipped,
                "duplicates": run.duplicates,
                "errors_count": len(run.errors) if run.errors else 0
            }
        else:
            result_data["run"] = None

    # 4. Querying TASK_UPDATES
    elif s_query.source == "task_updates":
        # Get list of tasks updated multiple times
        query = db.query(TaskUpdate.thread_id, func.count(TaskUpdate.id).label("update_count")).\
            filter(TaskUpdate.thread_id.is_not(None)).\
            group_by(TaskUpdate.thread_id)
            
        updates = query.all()
        multiple_updates = [u[0] for u in updates if u[1] > 1]
        
        result_data["threads_updated_multiple_times"] = multiple_updates
        result_data["all_thread_update_counts"] = {u[0]: u[1] for u in updates}

    return result_data

def generate_fallback_answer(s_query: StructuredChatQuery, data: Dict[str, Any]) -> str:
    """
    Generates a deterministic fallback answer from supporting_data if Gemini phrasing fails.
    """
    if "error" in data:
        return data["message"]
        
    scope_str = "in the current batch" if s_query.scope == "current_batch" else "across all history"

    if s_query.intent == "count":
        cnt = data.get("count", 0)
        source_name = "task" if s_query.source == "tasks" else "email"
        filter_str = f" matching {json.dumps(s_query.filters)}" if s_query.filters else ""
        return f"There are {cnt} {source_name}s{filter_str} {scope_str}."
        
    elif s_query.intent == "list":
        if s_query.source == "tasks":
            tasks = data.get("tasks", [])
            if not tasks:
                return f"No tasks were found {scope_str}."
            task_details = []
            for t in tasks:
                sender_str = f"From: {t['from_name']} ({t['from_email']}) | " if t.get('from_name') else ""
                details = f"- {t['title']} ({sender_str}Assignee: {t['assignee_id']}, Category: {t['category']}, Priority: {t['priority']}"
                if t.get('due_date'):
                    details += f", Due: {t['due_date']}"
                if t.get('deal_value_inr'):
                    details += f", Value: ₹{t['deal_value_inr']:,} INR"
                details += ")"
                task_details.append(details)
            return f"There are {len(tasks)} total tasks found {scope_str}. Here is the list:\n" + "\n".join(task_details)
        elif s_query.source == "processing_records":
            recs = data.get("records", [])
            if not recs:
                return f"No processed email records were found {scope_str}."
            rec_summaries = []
            for r in recs:
                rec_summaries.append(f"- Email {r['email_id']}: Decision: {r['decision']} (Reason: {r.get('reason', 'N/A')})")
            return f"There are {len(recs)} total processed records found {scope_str}. Here is the list:\n" + "\n".join(rec_summaries)

    elif s_query.intent == "rate" and "spurious_rate" in data:
        rate = data["spurious_rate"]
        processed = data["processed"]
        spurious = data["spurious_count"]
        return f"The spurious rate is {rate:.1%} ({spurious} spurious emails out of {processed} total processed)."
        
    elif s_query.intent == "aggregate" and "total_deal_value_inr" in data:
        val = data["total_deal_value_inr"]
        no_val = data["rfps_with_no_stated_value"]
        return f"The total deal value is ₹{val:,} INR, with {no_val} tasks having no stated budget value."
        
    elif s_query.intent == "thread_history":
        mults = data.get("threads_updated_multiple_times", [])
        if mults:
            return f"Yes, the following threads were updated more than once: {', '.join(mults)}."
        return "No threads were updated more than once."

    return "I found the matching data in the database but was unable to formulate a natural response. Please see supporting_data."

def answer_chat_query(candidate_id: str, query: str, db: Session) -> Dict[str, Any]:
    """
    Orchestrates the grounded chat pipeline:
    1. Parse query to structured JSON.
    2. Query DB to collect supporting_data.
    3. Generate response using Gemini grounded in supporting_data.
    """
    try:
        # Step 1: Parse user query
        s_query = parse_user_query(query)
    except Exception as e:
        logger.error(f"Failed to parse user query: {e}")
        # Default query representation on LLM failure using local fallback
        s_query = parse_user_query_fallback(query)

    # Step 2: Query PostgreSQL database
    supporting_data = execute_structured_query(candidate_id, s_query, db)

    # Step 3: Phrasing the response grounded in supporting_data
    prompt = f"""
You are an expert operations assistant answering questions about sales email routing statistics.
You MUST answer the user's question using ONLY the provided database query results (supporting_data).

Rules:
1. NEVER fabricate numbers or stats.
2. If the supporting_data indicates a count is 0, answer exactly 0. Do NOT guess or invent numbers.
3. If the user asks for a breakdown that is not in the data, state: "I don't have that breakdown in the stored processing data."
4. If the user asks you to send an email or take actions outside querying, state that you cannot do that.
5. DO NOT use markdown bolding or headers (like double asterisks '**' or '#'). Write clean plain text.
6. When returning a list of tasks or records, ALWAYS start your response with a summary count line stating the total number of matching items found (e.g., 'There are X total tasks/records found. Here is the list:' where X is the EXACT number of items present in the supporting_data tasks or records list), and you MUST list all of those matching items. Do NOT omit or filter out any item from the supporting_data array.

User Question: "{query}"
Supporting Data (from database):
{json.dumps(supporting_data, indent=2)}

Provide your response. Keep it concise and professional.
"""
    try:
        answer = call_gemini_with_retry(prompt, max_retries=3)
    except Exception as e:
        logger.warning(f"Gemini answer generation failed: {e}. Running deterministic fallback.")
        answer = generate_fallback_answer(s_query, supporting_data)

    return {
        "answer": answer,
        "supporting_data": supporting_data
    }

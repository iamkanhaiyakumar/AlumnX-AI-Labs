from datetime import datetime, timedelta

def calculate_priority(received_at: datetime, due_date_str: str, base_priority: str) -> str:
    """
    Checks if the stated deadline is within 72 hours of received_at.
    If so, returns 'high'. Otherwise, returns the base_priority.
    """
    if not due_date_str:
        return base_priority

    try:
        # Parse due date (YYYY-MM-DD)
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        
        # Calculate time difference
        # Normalize received_at to date-level or exact datetime if time is present in due_date.
        # Since due_date is just a date, we compare at the date level
        due_date_clean = due_date.date()
        received_date_clean = received_at.date()
        
        delta = due_date_clean - received_date_clean
        # Within 72 hours means <= 3 days and >= 0 days
        if 0 <= delta.days <= 3:
            return "high"
    except Exception:
        # Fallback to base priority if parsing fails
        pass

    return base_priority

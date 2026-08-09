import re
from typing import Dict, Any

def detect_spam_deterministic(subject: str, body: str) -> Dict[str, Any]:
    """
    Checks subject and body for deterministic signs of OOO, auto-replies, and newsletters.
    """
    subj_lower = subject.lower().strip()
    body_lower = body.lower().strip()

    # 1. Out of Office (OOO) and Auto-Replies
    ooo_prefixes = ["out of office", "ooo:", "automatic reply:", "autoreply:", "auto-reply:", "auto: out of office"]
    for pref in ooo_prefixes:
        if subj_lower.startswith(pref):
            return {
                "is_spam": True,
                "reason": "Out of Office or Auto-Reply subject prefix detected",
                "is_spurious": True,
                "type": "ooo"
            }

    ooo_body_patterns = [
        r"\bi\b.*\bout of office\b",
        r"\bi\b.*\bcurrently away\b",
        r"\blimited access to\b.*\bemail\b",
        r"\brespond when\b.*\breturn\b"
    ]
    for pat in ooo_body_patterns:
        if re.search(pat, body_lower):
            return {
                "is_spam": True,
                "reason": "Out of Office body indicator found",
                "is_spurious": True,
                "type": "ooo"
            }

    # 2. Newsletters
    newsletter_indicators = [
        r"\[unsubscribe\]",
        r"\bclick here to unsubscribe\b",
        r"\bview in browser\b",
        r"\bmanage your subscription\b",
        r"\bopt-out\b",
        r"\bpreferences\b.*\bemail\b"
    ]
    for pat in newsletter_indicators:
        if re.search(pat, body_lower):
            return {
                "is_spam": True,
                "reason": "Newsletter unsubscribe link or footer footer found",
                "is_spurious": True,
                "type": "newsletter"
            }

    return {"is_spam": False}
